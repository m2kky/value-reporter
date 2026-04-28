from __future__ import annotations

from datetime import date, datetime, timedelta
import asyncio
from typing import Any

from .config import OrganicConfig
from .graph_client import GraphApiError, GraphClient
from .base_client import PlatformApiError
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
    except (GraphApiError, PlatformApiError):
        # Don't log for the grouped fetch failure to reduce spam
        pass

    results: dict[str, float] = {}
    for metric in metrics:
        try:
            results.update(
                _flatten_insights(await graph.get(f"/{object_id}/insights", {"metric": metric}))
            )
        except (GraphApiError, PlatformApiError):
            # Suppress logs for metrics known to be deprecated on newer API versions
            deprecated_or_optional = [
                "post_engaged_users", "post_negative_feedback",
                "post_impressions", "post_reactions_by_type_total",
                "post_video_views", "post_media_view",
                "plays", "ig_reels_aggregated_all_plays_count",
            ]
            if metric not in deprecated_or_optional:
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
        
        # Fetch Instagram Stories
        try:
            instagram_token = organic.instagram_access_token or page_token
            instagram_graph = GraphClient(access_token=instagram_token, api_version=api_version)
            stories_rows = await _fetch_instagram_stories(instagram_graph, organic, diagnostics)
            rows.extend(stories_rows)
        except Exception as error:
            diagnostics["warnings"].append(f"Instagram Stories fetch failed: {error}")

    return rows, diagnostics


async def fetch_audience_demographics(
    organic: OrganicConfig,
    api_version: str,
) -> dict[str, Any]:
    audience_data = {
        "facebook": {},
        "instagram": {},
        "warnings": []
    }
    if not organic.enabled or not organic.page_id or not organic.access_token:
        audience_data["warnings"].append("Audience fetch skipped: missing page ID or access token.")
        return audience_data

    page_token = await _get_page_token(organic.access_token, organic.page_id, api_version)
    
    if organic.facebook_enabled:
        try:
            facebook_graph = GraphClient(access_token=page_token, api_version=api_version)
            fb_res = await _fetch_insights_resilient(
                facebook_graph, 
                organic.page_id, 
                ["page_fans_gender_age", "page_fans_city", "page_fans_country"], 
                audience_data["warnings"]
            )
            audience_data["facebook"] = fb_res
        except Exception as error:
            audience_data["warnings"].append(f"Facebook audience fetch failed: {error}")
            
    if organic.instagram_enabled:
        try:
            instagram_token = organic.instagram_access_token or page_token
            instagram_graph = GraphClient(access_token=instagram_token, api_version=api_version)
            ig_id = organic.instagram_account_id
            if not ig_id:
                try:
                    account = await instagram_graph.get(f"/{organic.page_id}", {"fields": "instagram_business_account{id}"})
                    ig_account = account.get("instagram_business_account") or {}
                    ig_id = ig_account.get("id")
                except Exception:
                    pass
            
            if ig_id:
                ig_metrics = "follower_demographics"
                ig_res = await instagram_graph.get(f"/{ig_id}/insights", {
                    "metric": ig_metrics, 
                    "period": "lifetime",
                    "metric_type": "total_value",
                    "breakdown": "age,gender"
                })
                # We need to grab age/gender, and maybe separately fetch city/country
                audience_data["instagram"] = _flatten_insights(ig_res)
        except Exception as error:
            audience_data["warnings"].append(f"Instagram audience fetch failed: {error}")

    return audience_data


async def fetch_page_level_insights(
    organic: OrganicConfig,
    api_version: str,
    since: date,
    until: date,
) -> dict[str, Any]:
    """Fetch page-level growth metrics (fans, page views, reach) via read_insights permission."""
    result: dict[str, Any] = {"warnings": []}
    if not organic.enabled or not organic.page_id or not organic.access_token:
        result["warnings"].append("Page insights skipped: missing page ID or access token.")
        return result

    page_token = await _get_page_token(organic.access_token, organic.page_id, api_version)
    graph = GraphClient(access_token=page_token, api_version=api_version)

    # Daily metrics aggregated over the period
    daily_metrics = [
        "page_impressions",
        "page_impressions_unique",
        "page_post_engagements",
        "page_video_views",
        "page_views_total",
        "page_fan_adds",
        "page_fan_removes",
        "page_fans_online",
    ]

    for metric in daily_metrics:
        try:
            res = await graph.get(f"/{organic.page_id}/insights", {
                "metric": metric,
                "period": "day",
                "since": since.isoformat(),
                "until": (until + timedelta(days=1)).isoformat(),
            })
            values = []
            for item in res.get("data", []):
                for v in item.get("values", []):
                    val = v.get("value")
                    if isinstance(val, (int, float)):
                        values.append(val)
            result[metric] = sum(values)
            result[f"{metric}_daily"] = values
        except Exception as error:
            result["warnings"].append(f"Page metric '{metric}' failed: {error}")

    # Lifetime metrics (total fans)
    lifetime_metrics = ["page_fans"]
    for metric in lifetime_metrics:
        try:
            res = await graph.get(f"/{organic.page_id}/insights", {
                "metric": metric,
                "period": "day",
                "since": until.isoformat(),
                "until": (until + timedelta(days=1)).isoformat(),
            })
            for item in res.get("data", []):
                vals = item.get("values", [])
                if vals:
                    result[metric] = vals[-1].get("value", 0)
        except Exception as error:
            result["warnings"].append(f"Page metric '{metric}' failed: {error}")

    return result


async def fetch_page_info(
    organic: OrganicConfig,
    api_version: str,
) -> dict[str, Any]:
    """Fetch page metadata (name, category, picture, followers) via pages_manage_metadata."""
    info: dict[str, Any] = {"warnings": []}
    if not organic.enabled or not organic.page_id or not organic.access_token:
        return info

    page_token = await _get_page_token(organic.access_token, organic.page_id, api_version)
    graph = GraphClient(access_token=page_token, api_version=api_version)

    try:
        data = await graph.get(f"/{organic.page_id}", {
            "fields": "name,category,fan_count,followers_count,picture{url},cover{source},about,website,phone"
        })
        info["name"] = data.get("name", "")
        info["category"] = data.get("category", "")
        info["fan_count"] = data.get("fan_count", 0)
        info["followers_count"] = data.get("followers_count", 0)
        info["picture_url"] = (data.get("picture", {}).get("data", {}) or {}).get("url", "")
        info["cover_url"] = (data.get("cover", {}) or {}).get("source", "")
        info["about"] = data.get("about", "")
        info["website"] = data.get("website", "")
        info["phone"] = data.get("phone", "")
    except Exception as error:
        info["warnings"].append(f"Page info fetch failed: {error}")

    # Also fetch IG profile info
    if organic.instagram_enabled:
        try:
            ig_token = organic.instagram_access_token or page_token
            ig_graph = GraphClient(access_token=ig_token, api_version=api_version)
            ig_id = organic.instagram_account_id
            if not ig_id:
                acct = await ig_graph.get(f"/{organic.page_id}", {"fields": "instagram_business_account{id}"})
                ig_id = (acct.get("instagram_business_account") or {}).get("id")
            if ig_id:
                ig_data = await ig_graph.get(f"/{ig_id}", {
                    "fields": "username,name,followers_count,media_count,profile_picture_url,biography"
                })
                info["instagram"] = {
                    "username": ig_data.get("username", ""),
                    "name": ig_data.get("name", ""),
                    "followers_count": ig_data.get("followers_count", 0),
                    "media_count": ig_data.get("media_count", 0),
                    "profile_picture_url": ig_data.get("profile_picture_url", ""),
                    "biography": ig_data.get("biography", ""),
                }
        except Exception as error:
            info["warnings"].append(f"Instagram profile info failed: {error}")

    return info


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
            "full_picture",
            "status_type",
            "shares",
            "comments.summary(true).limit(5)",
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
        
        # Reactions: try insight metric first, then Graph edge summary
        reactions_from_insights = 0
        reactions_breakdown = insights.get("post_reactions_by_type_total")
        if isinstance(reactions_breakdown, dict):
            reactions_from_insights = sum(reactions_breakdown.values())
        elif isinstance(reactions_breakdown, (int, float)):
            reactions_from_insights = int(reactions_breakdown)
        if reactions_from_insights > 0:
            reactions = reactions_from_insights
        
        # Views priority: post_media_view (new) > video_views > post_impressions > reach
        views = (
            insights.get("post_media_view", 0) or
            insights.get("post_video_views", 0) or
            insights.get("post_video_views_organic", 0) or
            insights.get("post_impressions", 0) or
            reach
        )
        
        engagement = comments + reactions + shares
        
        # Extract comment texts
        comment_texts = []
        for c in post.get("comments", {}).get("data", []):
            if c.get("message"):
                comment_texts.append(c.get("message"))
                
        normalized.append(
            {
                "platform": "facebook",
                "content_id": post.get("id", ""),
                "created_time": post.get("created_time", ""),
                "content_format": _facebook_format(post),
                "content_topic": classify_topic(text),
                "text_preview": text[:180].replace("\n", " "),
                "permalink": post.get("permalink_url", ""),
                "thumbnail_url": post.get("full_picture", ""),
                "views": views,
                "reach": reach,
                "likes": reactions,
                "comments": comments,
                "shares": shares,
                "saves": 0,
                "engagements": engagement,
                "engagement_rate": engagement / reach if reach else 0,
                "top_comments": comment_texts,
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
            "comments.limit(5){text}",
            "media_url",
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
        
        # Meta Business Suite often uses plays/video_views for Reels
        plays = insights.get("plays", 0) or insights.get("ig_reels_aggregated_all_plays_count", 0)
        views = plays if plays > 0 else (insights.get("views", 0) or reach)
        
        engagement = to_float(insights.get("total_interactions") or (likes + comments + shares + saves))
        
        # Extract comment texts
        comment_texts = []
        for c in media.get("comments", {}).get("data", []):
            if c.get("text"):
                comment_texts.append(c.get("text"))

        normalized.append(
            {
                "platform": "instagram",
                "content_id": media.get("id", ""),
                "created_time": str(timestamp),
                "content_format": _instagram_format(media),
                "content_topic": classify_topic(text),
                "text_preview": text[:180].replace("\n", " "),
                "permalink": media.get("permalink", ""),
                "thumbnail_url": media.get("thumbnail_url") or media.get("media_url", ""),
                "views": views,
                "reach": reach,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "saves": saves,
                "engagements": engagement,
                "engagement_rate": engagement / reach if reach else 0,
                "top_comments": comment_texts,
            }
        )
    return normalized


async def _fetch_instagram_stories(
    graph: GraphClient,
    organic: OrganicConfig,
    diagnostics: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fetch currently live Instagram Stories (last 24h).

    Note: Instagram Graph API only exposes stories that are currently live.
    Historical stories are not available via the API.
    """
    ig_id = organic.instagram_account_id
    if not ig_id:
        try:
            account = await graph.get(
                f"/{organic.page_id}",
                {"fields": "instagram_business_account{id}"},
            )
            ig_id = (account.get("instagram_business_account") or {}).get("id")
        except Exception:
            return []
    if not ig_id:
        return []

    try:
        stories_res = await graph.get(
            f"/{ig_id}/stories",
            {"fields": "id,caption,media_type,permalink,timestamp"},
        )
    except (GraphApiError, PlatformApiError) as error:
        diagnostics["warnings"].append(f"Instagram Stories fetch skipped: {error}")
        return []

    stories = stories_res.get("data", [])
    if not stories:
        return []

    normalized = []
    for story in stories:
        story_id = str(story.get("id"))
        # Fetch insights for each story
        insights = {}
        try:
            insights = _flatten_insights(
                await graph.get(f"/{story_id}/insights", {"metric": "reach,replies,exits,impressions"})
            )
        except Exception:
            pass

        reach = to_float(insights.get("reach"))
        impressions = to_float(insights.get("impressions") or reach)
        replies = to_int(insights.get("replies"))
        exits = to_int(insights.get("exits"))

        normalized.append(
            {
                "platform": "instagram_stories",
                "content_id": story_id,
                "created_time": story.get("timestamp", ""),
                "content_format": "STORY",
                "content_topic": "Story",
                "text_preview": (story.get("caption") or "")[:180].replace("\n", " "),
                "permalink": story.get("permalink", ""),
                "views": impressions,
                "reach": reach,
                "likes": replies,  # Stories don't have likes; use replies as engagement proxy
                "comments": 0,
                "shares": 0,
                "saves": 0,
                "engagements": replies,
                "engagement_rate": replies / reach if reach else 0,
                "exits": exits,
                "top_comments": [],
            }
        )
    return normalized
