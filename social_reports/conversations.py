"""Module to fetch and analyze Facebook Page conversations."""

import logging
from typing import Any
from datetime import datetime, date, timezone
from dateutil.parser import parse as parse_date

from .graph_client import GraphClient
from .config_parser import OrganicConfig

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
        # Fetch up to 15 recent conversations and their messages
        url = f"/{organic.page_id}/conversations"
        params = {
            "fields": "messages{message,from,created_time,to}",
            "limit": "15"
        }
        
        response = await graph.get(url, params)
        conversations = response.get("data", [])
        
    except Exception as error:
        diagnostics["warnings"].append(f"Conversations fetch failed (ensure token has pages_messaging permission): {error}")
        return {"diagnostics": diagnostics}

    total_conversations = len(conversations)
    messages_received = 0
    messages_sent = 0
    response_times = []  # in seconds
    responded_conversations = 0

    for conv in conversations:
        messages = conv.get("messages", {}).get("data", [])
        if not messages:
            continue
            
        # Sort messages oldest to newest
        messages.sort(key=lambda m: m.get("created_time", ""))
        
        customer_msg_time = None
        has_reply = False
        
        for msg in messages:
            sender = msg.get("from", {}).get("id")
            created_time_str = msg.get("created_time")
            if not created_time_str:
                continue
                
            msg_time = parse_date(created_time_str)
            
            # If sender is not the page
            if sender != organic.page_id:
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

    avg_response_time_seconds = 0
    if response_times:
        avg_response_time_seconds = sum(response_times) / len(response_times)

    response_rate = 0
    if total_conversations > 0:
        response_rate = (responded_conversations / total_conversations) * 100

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
        "diagnostics": diagnostics
    }
