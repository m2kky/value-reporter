"""Module to fetch and analyze Facebook Lead Generation Forms."""

import logging
from typing import Any
from datetime import datetime, date, timezone
from .organic import parse_graph_time, _get_page_token

from .graph_client import GraphClient
from .config import OrganicConfig

logger = logging.getLogger(__name__)

async def fetch_leads(
    organic: OrganicConfig,
    *,
    api_version: str,
    since: date,
    until: date,
) -> dict[str, Any]:
    """Fetch lead generation forms and count leads within the period."""
    diagnostics = {"warnings": []}
    
    if not organic.enabled or not organic.facebook_enabled or not organic.page_id:
        return {"forms": [], "total_leads": 0, "diagnostics": diagnostics}

    if not organic.access_token:
        diagnostics["warnings"].append("Missing access token for leads.")
        return {"forms": [], "total_leads": 0, "diagnostics": diagnostics}

    page_token = await _get_page_token(organic.access_token, organic.page_id, api_version)
    graph = GraphClient(access_token=page_token, api_version=api_version)
    
    forms_data = []
    total_leads = 0
    
    try:
        # Fetch all leadgen forms for the page
        url = f"/{organic.page_id}/leadgen_forms"
        params = {
            "fields": "id,name,status,leads_count,created_time",
            "limit": "50"
        }
        
        forms = await graph.get_paginated(url, params, max_rows=100)
        
        for form in forms:
            form_id = form.get("id")
            form_name = form.get("name", "Unknown Form")
            status = form.get("status", "")
            
            # Fetch leads for this specific form within the date range
            # Note: We can filter leads by time created
            since_time = int(datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc).timestamp())
            until_time = int(datetime.combine(until, datetime.max.time(), tzinfo=timezone.utc).timestamp())
            
            leads_url = f"/{form_id}/leads"
            leads_params = {
                "filtering": f"[{__import__('json').dumps({'field':'time_created','operator':'GREATER_THAN','value':since_time})},{__import__('json').dumps({'field':'time_created','operator':'LESS_THAN','value':until_time})}]",
                "limit": "100"
            }
            
            try:
                # We just need the count, but paginated fetch gets all of them.
                # If there are thousands of leads, this might be slow, so we limit to max_rows=1000
                leads = await graph.get_paginated(leads_url, leads_params, max_rows=1000)
                period_leads = len(leads)
                
                if period_leads > 0:
                    forms_data.append({
                        "id": form_id,
                        "name": form_name,
                        "status": status,
                        "leads_in_period": period_leads,
                        "lifetime_leads": form.get("leads_count", 0)
                    })
                    total_leads += period_leads
            except Exception as e:
                diagnostics["warnings"].append(f"Failed to fetch leads for form {form_id}: {e}")

    except Exception as error:
        diagnostics["warnings"].append(f"Leadgen forms fetch failed (ensure token has leads_retrieval and pages_manage_ads): {error}")

    return {
        "forms": sorted(forms_data, key=lambda x: x["leads_in_period"], reverse=True),
        "total_leads": total_leads,
        "diagnostics": diagnostics
    }
