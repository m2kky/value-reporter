import logging
from typing import Dict, Any, List
from datetime import datetime
import aiohttp

from .tiktok_client import TikTokClient, TikTokApiError

logger = logging.getLogger(__name__)

USER_INFO_FIELDS = [
    "open_id", "union_id", "avatar_url", "display_name",
    "follower_count", "following_count", "likes_count", "video_count"
]

VIDEO_FIELDS = [
    "id", "create_time", "cover_image_url", "share_url", "video_description",
    "duration", "title",
    "like_count", "comment_count", "share_count", "view_count"
]

async def fetch_tiktok_profile(client: TikTokClient) -> Dict[str, Any]:
    """Fetch TikTok user profile and stats"""
    try:
        data = await client.get("/user/info/", fields=USER_INFO_FIELDS)
        return data.get("user", {})
    except TikTokApiError as e:
        logger.error(f"Failed to fetch TikTok profile: {e}")
        return {}

async def fetch_tiktok_videos(client: TikTokClient, max_videos: int = 50) -> List[Dict[str, Any]]:
    """Fetch TikTok videos for the authenticated user"""
    videos = []
    cursor = None
    has_more = True
    
    while len(videos) < max_videos and has_more:
        body = {"max_count": min(20, max_videos - len(videos))}
        if cursor is not None:
            body["cursor"] = cursor
            
        try:
            data = await client.post("/video/list/", fields=VIDEO_FIELDS, body=body)
            new_videos = data.get("videos", [])
            videos.extend(new_videos)
            
            has_more = data.get("has_more", False)
            cursor = data.get("cursor")
            
            if not has_more or not cursor:
                break
                
        except TikTokApiError as e:
            logger.error(f"Failed to fetch TikTok videos: {e}")
            break
            
    return videos

async def run_tiktok_pipeline(access_token: str, max_videos: int = 50) -> Dict[str, Any]:
    """Run the TikTok data fetching pipeline"""
    client = TikTokClient(access_token=access_token)
    
    try:
        logger.info("Fetching TikTok profile stats...")
        profile = await fetch_tiktok_profile(client)
        
        logger.info("Fetching TikTok videos...")
        videos = await fetch_tiktok_videos(client, max_videos=max_videos)
        logger.info(f"Fetched {len(videos)} TikTok videos")
        
        return {
            "profile": profile,
            "videos": videos
        }
    finally:
        await client.close()
