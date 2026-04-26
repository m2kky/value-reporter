from __future__ import annotations

from datetime import date, datetime, timedelta
import asyncio
from typing import Any

from .config import OrganicConfig
from .graph_client import GraphApiError, GraphClient
from .normalize import to_float, to_int


def parse_graph_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _summary_total(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    return to_int(value.get("summary", {}).get("total_count"))


def _share_count(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    return to_int(value.get("count"))


def repair_mojibake(value: str) -> str:
    markers = ("Ø", "Ù", "ðŸ", "â€", "ï¸")
    if not value or not any(marker in value for marker in markers):
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value


def _flatten_insights(payload: dict[str, Any]) -> dict[str, float]:
    flat: dict[str, float] = {}
    for item in payload.get("data", []):
        name = item.get("name")
        values = item.get("values", [])
        if not name or not values:
            continue
        value = values[-1].get("value")
        if isinstance(value, dict):
            flat[name] = sum(to_float(v) for v in value.values())
            for key, nested_value in value.items():
                flat[f"{name}_{key}"] = to_float(nested_value)
        else:
            flat[name] = to_float(value)
    return flat


async def _fetch_insights_resilient(
    graph: GraphClient,
    object_id: str,
    metrics: list[str],
    warnings: list[str],
) -> dict[str, float]:
    if not metrics:
        return {}
    try:
        return _flatten_insights(
            await graph.get(f"/{object_id}/insights", {"metric": ",".join(metrics)})
        )
    except GraphApiError as error:
        warnings.append(f"{object_id}: grouped insights failed; retrying individual metrics.")

    results: dict[str, float] = {}
    for metric in metrics:
        try:
            results.update(
                _flatten_insights(await graph.get(f"/{object_id}/insights", {"metric": metric}))
            )
        except GraphApiError:
            warnings.append(f"{object_id}: metric '{metric}' unavailable.")
    return results


def _content_text(row: dict[str, Any]) -> str:
    return repair_mojibake(str(row.get("message") or row.get("caption") or row.get("story") or ""))


def classify_topic(text: str) -> str:
    lowered = text.lower()
    topic_keywords = [
        ("Offer/Promo", ["offer", "discount", "sale", "promo", "خصم", "عرض", "عروض", "وفر", "كوبون"]),
        ("Product/Menu", ["menu", "product", "price", "منيو", "سعر", "طبق", "وجبة", "كافيه", "مطعم", "منتج"]),
        ("Social Proof", ["review", "testimonial", "customer", "client", "تقييم", "رأي", "عميل", "تجربة"]),
        ("Educational", ["tips", "guide", "how to", "نصائح", "طريقة", "اعرف", "ازاي", "خطوات"]),
        ("Event/Seasonal", ["event", "opening", "ramadan", "eid", "افتتاح", "رمضان", "عيد", "فرع", "موسم"]),
        ("Community", ["comment", "vote", "question", "قولنا", "شارك", "اكتب", "مين", "اختار"]),
        ("Hiring", ["hiring", "job", "career", "مطلوب", "وظيفة", "انضم", "توظيف"]),
    ]
    for topic, keywords in topic_keywords:
        if any(keyword in lowered for keyword in keywords):
            return topic
    return "General Brand"


def _facebook_format(post: dict[str, Any]) -> str:
    attachment = {}
    attachments = post.get("attachments", {}).get("data", [])
    if attachments:
        attachment = attachments[0]
    raw = str(attachment.get("media_type") or attachment.get("type") or post.get("status_type") or "text")
    raw = raw.upper()
    if "VIDEO" in raw:
        return "VIDEO"
    if "PHOTO" in raw or "IMAGE" in raw:
        return "IMAGE"
    if "ALBUM" in raw or "CAROUSEL" in raw:
        return "CAROUSEL"
    if "LINK" in raw:
        return "LINK"
    return "TEXT"


def _instagram_format(media: dict[str, Any]) -> str:
    product = str(media.get("media_product_type") or "").upper()
    media_type = str(media.get("media_type") or "").upper()
    if product == "REELS":
        return "REEL"
    if media_type == "CAROUSEL_ALBUM":
        return "CAROUSEL"
    if media_type == "VIDEO":
        return "VIDEO"
    if media_type == "IMAGE":
        return "IMAGE"
    return product or media_type or "UNKNOWN"


async def _get_page_token(
    user_token: str, page_id: str, api_version: str
) -> str:
    """Exchange a User Access Token for a Page Access Token.
    
    Meta's new Pages experience requires a Page token for
    /{page_id}/posts and insights. If the token is already a
    Page token, the exchange returns the same value harmlessly.
    """
    graph = GraphClient(access_token=user_token, api_version=api_version)
    try:
        result = await graph.get(f"/{page_id}", {"fields": "access_token"})
        page_token = result.get("access_token")
        if page_token:
            return page_token
    except Exception:
        pass  # Fall through to return original token
    return user_token


async def fetch_organic_content(
    organic: OrganicConfig,
    *,
    api_version: str,
    since: date,
    until: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    diagnostics: dict[str, Any] = {
        "warnings": [],
        "facebook_posts_raw": [],
        "facebook_post_insights_raw": {},
        "instagram_account_raw": {},
        "instagram_media_raw": [],
        "instagram_media_insights_raw": {},
    }

    if not organic.enabled or not organic.page_id or not organic.access_token:
        diagnostics["warnings"].append("Organic connector skipped: missing page ID or organic access token.")
        return [], diagnostics

    # Auto-exchange User token → Page token (required by Meta's new Pages experience)
    page_token = await _get_page_token(organic.access_token, organic.page_id, api_version)

    rows: list[dict[str, Any]] = []

    if organic.facebook_enabled:
        try:
            facebook_graph = GraphClient(access_token=page_token, api_version=api_version)
            fb_rows = await _fetch_facebook_posts(facebook_graph, organic, since, until, diagnostics)
            rows.extend(fb_rows)
        except Exception as error:
            diagnostics["warnings"].append(f"Facebook fetch failed: {error}")

    if organic.instagram_enabled:
        try:
            instagram_token = organic.instagram_access_token or page_token
            instagram_graph = GraphClient(access_token=instagram_token, api_version=api_version)
            ig_rows = await _fetch_instagram_media(instagram_graph, organic, since, until, diagnostics)
            rows.extend(ig_rows)
        except Exception as error:
            diagnostics["warnings"].append(f"Instagram fetch failed: {error}")

    return rows, diagnostics


async def _fetch_facebook_posts(
    graph: GraphClient,
    organic: OrganicConfig,
    since: date,
    until: date,
    diagnostics: dict[str, Any],
) -> list[dict[str, Any]]:
    until_exclusive = until + timedelta(days=1)
    fields = ",".join(
        [
            "id",
            "message",
            "story",
            "created_time",
            "permalink_url",
            "status_type",
            "shares",
            "comments.summary(true).limit(0)",
            "reactions.summary(true).limit(0)",
            "attachments{media_type,type,title,url}",
        ]
    )
    try:
        posts = await graph.get_paginated(
            f"/{organic.page_id}/posts",
            {
                "fields": fields,
                "since": since.isoformat(),
                "until": until_exclusive.isoformat(),
                "limit": 25,
            },
            max_rows=organic.max_facebook_posts,
        )
    except GraphApiError as error:
        diagnostics["warnings"].append(f"Facebook posts skipped: {error}")
        return []

    diagnostics["facebook_posts_raw"] = posts
    normalized = []
    for post in posts:
        insights = await _fetch_insights_resilient(
            graph,
            str(post.get("id")),
            organic.facebook_post_insight_metrics,
            diagnostics["warnings"],
        )
        diagnostics["facebook_post_insights_raw"][str(post.get("id"))] = insights
        text = _content_text(post)
        comments = _summary_total(post.get("comments"))
        reactions = _summary_total(post.get("reactions"))
        shares = _share_count(post.get("shares"))
        reach = insights.get("post_impressions_unique", 0)
        views = insights.get("post_impressions", 0) or reach
        engagement = insights.get("post_engaged_users") or (comments + reactions + shares)
        normalized.append(
            {
                "platform": "facebook",
                "content_id": post.get("id", ""),
                "created_time": post.get("created_time", ""),
                "content_format": _facebook_format(post),
                "content_topic": classify_topic(text),
                "text_preview": text[:180].replace("\n", " "),
                "permalink": post.get("permalink_url", ""),
                "views": views,
                "reach": reach,
                "likes": reactions,
                "comments": comments,
                "shares": shares,
                "saves": 0,
                "engagements": engagement,
                "engagement_rate": engagement / reach if reach else 0,
            }
        )
    return normalized


async def _fetch_instagram_media(
    graph: GraphClient,
    organic: OrganicConfig,
    since: date,
    until: date,
    diagnostics: dict[str, Any],
) -> list[dict[str, Any]]:
    ig_id = organic.instagram_account_id
    if ig_id:
        diagnostics["instagram_account_raw"] = {"id": ig_id, "source": organic.instagram_account_id_env}
    else:
        try:
            account = await graph.get(
                f"/{organic.page_id}",
                {"fields": "instagram_business_account{id,username,name,followers_count,media_count}"},
            )
        except GraphApiError as error:
            diagnostics["warnings"].append(f"Instagram account lookup skipped: {error}")
            return []

        diagnostics["instagram_account_raw"] = account
        ig_account = account.get("instagram_business_account") or {}
        ig_id = ig_account.get("id")
    if not ig_id:
        diagnostics["warnings"].append("Instagram skipped: no instagram_business_account found on the Page.")
        return []

    fields = ",".join(
        [
            "id",
            "caption",
            "media_type",
            "media_product_type",
            "permalink",
            "timestamp",
            "like_count",
            "comments_count",
            "thumbnail_url",
        ]
    )
    try:
        media_rows = await graph.get_paginated(
            f"/{ig_id}/media",
            {"fields": fields, "limit": 25},
            max_rows=organic.max_instagram_media,
        )
    except GraphApiError as error:
        diagnostics["warnings"].append(f"Instagram media skipped: {error}")
        return []

    start_dt = datetime.combine(since, datetime.min.time()).replace(tzinfo=None)
    end_dt = datetime.combine(until + timedelta(days=1), datetime.min.time()).replace(tzinfo=None)
    filtered = []
    for media in media_rows:
        timestamp = parse_graph_time(str(media.get("timestamp", "")))
        if not timestamp:
            continue
        timestamp_naive = timestamp.replace(tzinfo=None)
        if start_dt <= timestamp_naive < end_dt:
            filtered.append(media)

    diagnostics["instagram_media_raw"] = filtered
    normalized = []
    for media in filtered:
        media_id = str(media.get("id"))
        insights = await _fetch_insights_resilient(
            graph,
            media_id,
            organic.instagram_media_insight_metrics,
            diagnostics["warnings"],
        )
        diagnostics["instagram_media_insights_raw"][media_id] = insights
        text = _content_text(media)
        comments = to_int(insights.get("comments") or media.get("comments_count"))
        likes = to_int(insights.get("likes") or media.get("like_count"))
        shares = to_int(insights.get("shares"))
        saves = to_int(insights.get("saved"))
        reach = to_float(insights.get("reach"))
        views = to_float(insights.get("views") or reach)
        engagements = to_float(insights.get("total_interactions") or (likes + comments + shares + saves))
        normalized.append(
            {
                "platform": "instagram",
                "content_id": media_id,
                "created_time": media.get("timestamp", ""),
                "content_format": _instagram_format(media),
                "content_topic": classify_topic(text),
                "text_preview": text[:180].replace("\n", " "),
                "permalink": media.get("permalink", ""),
                "views": views,
                "reach": reach,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "saves": saves,
                "engagements": engagements,
                "engagement_rate": engagements / reach if reach else 0,
            }
        )
    return normalized
