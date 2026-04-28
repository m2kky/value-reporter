"""Module to fetch and analyze Facebook Page conversations."""

import logging
from typing import Any
from datetime import datetime, date, timezone
from .organic import parse_graph_time

from .graph_client import GraphClient
from .config import OrganicConfig

logger = logging.getLogger(__name__)

async def fetch_conversations(
    organic: OrganicConfig,
    *,
    api_version: str,
    since: date,
    until: date,
) -> dict[str, Any]:
    """Fetch the latest conversations and analyze response times."""
    diagnostics = {"warnings": []}
    
    if not organic.enabled or not organic.facebook_enabled or not organic.page_id:
        return {"diagnostics": diagnostics}

    if not organic.access_token:
        diagnostics["warnings"].append("Missing access token for conversations.")
        return {"diagnostics": diagnostics}

    # Use the same token exchange logic from organic.py to get a Page Token
    from .organic import _get_page_token
    page_token = await _get_page_token(organic.access_token, organic.page_id, api_version)
    
    graph = GraphClient(access_token=page_token, api_version=api_version)
    
    try:
        # Fetch Facebook conversations
        fb_url = f"/{organic.page_id}/conversations"
        fb_params = {
            "fields": "messages{message,from,created_time,to}",
            "limit": "50"
        }
        fb_conversations = await graph.get_paginated(fb_url, fb_params, max_rows=100)
    except Exception as error:
        diagnostics["warnings"].append(f"FB Conversations fetch failed: {error}")
        fb_conversations = []

    ig_conversations = []
    if organic.instagram_enabled:
        ig_id = organic.instagram_account_id
        if not ig_id:
            try:
                acct = await graph.get(f"/{organic.page_id}", {"fields": "instagram_business_account{id}"})
                ig_id = (acct.get("instagram_business_account") or {}).get("id")
            except Exception:
                pass
                
        if ig_id:
            try:
                ig_url = f"/{ig_id}/conversations"
                ig_params = {
                    "platform": "instagram",
                    "fields": "messages{message,from,created_time,to}",
                    "limit": "50"
                }
                ig_conversations = await graph.get_paginated(ig_url, ig_params, max_rows=100)
            except Exception as error:
                diagnostics["warnings"].append(f"IG Conversations fetch failed (needs instagram_manage_messages): {error}")

    wa_conversations_count = 0
    if hasattr(organic, "whatsapp_business_account_id") and organic.whatsapp_business_account_id:
        try:
            # WhatsApp Cloud API does not expose historical message text via Graph API.
            # We fetch analytics instead (requires whatsapp_business_management)
            wa_id = organic.whatsapp_business_account_id
            wa_res = await graph.get(f"/{wa_id}/conversation_analytics", {
                "start": int(datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc).timestamp()),
                "end": int(datetime.combine(until, datetime.max.time(), tzinfo=timezone.utc).timestamp()),
                "granularity": "MONTH"
            })
            for dp in wa_res.get("data", []):
                for dp_inner in dp.get("data_points", []):
                    wa_conversations_count += dp_inner.get("conversation", 0)
        except Exception as error:
            diagnostics["warnings"].append(f"WhatsApp Analytics fetch failed (check ID and permissions): {error}")

    all_conversations = fb_conversations + ig_conversations
    total_conversations = len(all_conversations)
    messages_received = 0
    messages_sent = 0
    response_times = []  # in seconds
    responded_conversations = 0
    
    # Store transcripts for AI analysis
    transcripts = {
        "facebook": [],
        "instagram": [],
        "whatsapp": ["WhatsApp message transcripts cannot be fetched historically via the Meta API. They require real-time Webhook infrastructure (like ValueWats)."]
    }

    for conv in all_conversations:
        messages = conv.get("messages", {}).get("data", [])
        if not messages:
            continue
            
        # Sort messages oldest to newest
        messages.sort(key=lambda m: m.get("created_time", ""))
        
        customer_msg_time = None
        has_reply = False
        
        platform = "facebook"
        if conv in ig_conversations:
            platform = "instagram"
            
        transcript_lines = []
        
        for msg in messages:
            sender = msg.get("from", {}).get("id")
            created_time_str = msg.get("created_time")
            text = msg.get("message", "")
            
            if not created_time_str:
                continue
                
            msg_time = parse_graph_time(created_time_str)
            if not msg_time:
                continue
            
            # Identify if sender is the business
            is_business = (sender == organic.page_id) or (organic.instagram_enabled and sender == organic.instagram_account_id)
            
            if text:
                sender_name = "Business" if is_business else "Customer"
                transcript_lines.append(f"{sender_name}: {text}")

            if not is_business:
                messages_received += 1
                if customer_msg_time is None:
                    customer_msg_time = msg_time
            else:
                messages_sent += 1
                # If page replied to a customer message
                if customer_msg_time is not None:
                    has_reply = True
                    delta = (msg_time - customer_msg_time).total_seconds()
                    if delta >= 0:
                        response_times.append(delta)
                    # Reset waiting for next customer message in thread
                    customer_msg_time = None

        if has_reply:
            responded_conversations += 1
            
        if transcript_lines:
            transcripts[platform].append("\n".join(transcript_lines[:15]))  # Keep up to 15 messages per convo for context

    avg_response_time_seconds = 0
    if response_times:
        avg_response_time_seconds = sum(response_times) / len(response_times)

    total_conversations += wa_conversations_count
    
    response_rate = 0
    if len(all_conversations) > 0:
        response_rate = (responded_conversations / len(all_conversations)) * 100

    # Format average response time for display
    avg_display = "N/A"
    if avg_response_time_seconds > 0:
        if avg_response_time_seconds < 60:
            avg_display = "< 1 minute"
        elif avg_response_time_seconds < 3600:
            avg_display = f"{int(avg_response_time_seconds // 60)} minutes"
        else:
            hours = avg_response_time_seconds / 3600
            avg_display = f"{hours:.1f} hours"

    return {
        "total_conversations": total_conversations,
        "messages_received": messages_received,
        "messages_sent": messages_sent,
        "response_rate": response_rate,
        "avg_response_time_seconds": avg_response_time_seconds,
        "avg_response_time_display": avg_display,
        "transcripts": transcripts,
        "diagnostics": diagnostics
    }
