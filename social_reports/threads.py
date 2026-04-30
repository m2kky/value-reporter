"""Threads data fetching logic — auto-detects Threads profile from token."""
import logging
from datetime import date, datetime
from typing import Any

from .threads_client import ThreadsClient, ThreadsApiError

logger = logging.getLogger(__name__)

# Per-post insight metrics
POST_METRICS = "views,likes,replies,reposts,quotes,shares"

# User-level insight metrics
USER_METRICS = "views,likes,replies,reposts,quotes"


async def detect_threads_profile(access_token: str) -> dict[str, Any] | None:
    """Try to detect a Threads profile using the given token.
    Returns profile dict if successful, None if token doesn't have Threads access.
    """
    client = ThreadsClient(access_token)
    try:
        profile = await client.get("/me", {
            "fields": "id,username,threads_profile_picture_url,threads_biography"
        })
        if profile.get("id"):
            logger.info(f"Threads profile detected: @{profile.get('username', '?')}")
            return profile
        return None
    except (ThreadsApiError, Exception) as e:
        logger.debug(f"Threads not available for this token: {e}")
        return None


async def fetch_threads_posts(
    access_token: str,
    threads_user_id: str,
    since: date,
    until: date,
    max_posts: int = 100,
) -> list[dict[str, Any]]:
    """Fetch Threads posts and their insights for a date range."""
    client = ThreadsClient(access_token)
    rows: list[dict[str, Any]] = []

    try:
        # Fetch user's threads
        result = await client.get(f"/{threads_user_id}/threads", {
            "fields": "id,media_product_type,media_type,media_url,permalink,text,timestamp,shortcode,thumbnail_url,is_quote_post",
            "limit": str(min(max_posts, 100)),
            "since": str(int(datetime.combine(since, datetime.min.time()).timestamp())),
            "until": str(int(datetime.combine(until, datetime.max.time()).timestamp())),
        })

        posts = result.get("data", [])
        logger.info(f"Fetched {len(posts)} Threads posts")

        # Fetch insights for each post
        for post in posts:
            post_id = post.get("id")
            if not post_id:
                continue

            # Parse timestamp
            ts = post.get("timestamp", "")
            try:
                created_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                created_at = datetime.now()

            # Fetch per-post insights
            metrics = {"views": 0, "likes": 0, "replies": 0, "reposts": 0, "quotes": 0, "shares": 0}
            try:
                insights = await client.get(f"/{post_id}/insights", {"metric": POST_METRICS})
                for item in insights.get("data", []):
                    name = item.get("name", "")
                    values = item.get("values", [])
                    if values:
                        metrics[name] = values[0].get("value", 0)
                    elif "total_value" in item:
                        metrics[name] = item["total_value"].get("value", 0)
            except (ThreadsApiError, Exception) as e:
                logger.debug(f"Could not fetch insights for Threads post {post_id}: {e}")

            engagement = metrics["likes"] + metrics["replies"] + metrics["reposts"] + metrics["quotes"] + metrics["shares"]

            rows.append({
                "id": post_id,
                "platform": "threads",
                "format": _thread_format(post),
                "created_at": created_at.isoformat(),
                "text": post.get("text", ""),
                "topic": "",  # Will be classified by organic.py's classify_topic
                "url": post.get("permalink", ""),
                "thumbnail_url": post.get("thumbnail_url", "") or post.get("media_url", ""),
                "reach": metrics["views"],
                "views": metrics["views"],
                "engagement": engagement,
                "likes": metrics["likes"],
                "comments": metrics["replies"],
                "shares": metrics["shares"] + metrics["reposts"],
                "saves": 0,
                "video_views": 0,
                "engagement_rate": round((engagement / metrics["views"]) * 100, 2) if metrics["views"] else 0,
                "comments_list": [],
                "raw_metrics": metrics,
            })

    except ThreadsApiError as e:
        logger.warning(f"Failed to fetch Threads posts: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error fetching Threads posts: {e}")

    return rows


def _thread_format(post: dict[str, Any]) -> str:
    media_type = str(post.get("media_type", "")).upper()
    if media_type == "VIDEO":
        return "VIDEO"
    if media_type == "IMAGE":
        return "IMAGE"
    if media_type == "CAROUSEL_ALBUM":
        return "CAROUSEL"
    if post.get("is_quote_post"):
        return "QUOTE"
    return "TEXT"


async def run_threads_pipeline(
    access_token: str,
    since: date,
    until: date,
    max_posts: int = 100,
) -> dict[str, Any]:
    """Auto-detect Threads and fetch posts if available.
    Returns {"available": True, "profile": {...}, "posts": [...]} or
            {"available": False}
    """
    profile = await detect_threads_profile(access_token)
    if not profile:
        return {"available": False}

    threads_user_id = profile["id"]
    posts = await fetch_threads_posts(access_token, threads_user_id, since, until, max_posts)

    return {
        "available": True,
        "profile": profile,
        "posts": posts,
    }
