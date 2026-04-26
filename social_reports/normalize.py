from __future__ import annotations

from typing import Any


PURCHASE_ACTIONS = {
    "purchase",
    "omni_purchase",
    "offsite_conversion.fb_pixel_purchase",
}

LEAD_ACTIONS = {
    "lead",
    "omni_lead",
    "onsite_conversion.lead_grouped",
    "offsite_conversion.fb_pixel_lead",
}


def to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def to_int(value: Any) -> int:
    return int(round(to_float(value)))


def action_total(actions: Any, names: set[str]) -> float:
    if not isinstance(actions, list):
        return 0.0
    total = 0.0
    for action in actions:
        if action.get("action_type") in names:
            total += to_float(action.get("value"))
    return total


def normalize_meta_rows(
    rows: list[dict[str, Any]],
    *,
    client_id: str,
    report_month: str,
    level: str,
    account_alias: str = "",
) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        spend = to_float(row.get("spend"))
        impressions = to_int(row.get("impressions"))
        reach = to_int(row.get("reach"))
        clicks = to_int(row.get("clicks"))
        inline_link_clicks = to_int(row.get("inline_link_clicks"))
        purchases = action_total(row.get("actions"), PURCHASE_ACTIONS)
        leads = action_total(row.get("actions"), LEAD_ACTIONS)
        purchase_value = action_total(row.get("action_values"), PURCHASE_ACTIONS)

        normalized.append(
            {
                "client_id": client_id,
                "report_month": report_month,
                "platform": "meta",
                "level": level,
                "account_alias": account_alias,
                "date_start": row.get("date_start", ""),
                "date_stop": row.get("date_stop", ""),
                "account_id": row.get("account_id", ""),
                "account_name": row.get("account_name", ""),
                "campaign_id": row.get("campaign_id", ""),
                "campaign_name": row.get("campaign_name", ""),
                "adset_id": row.get("adset_id", ""),
                "adset_name": row.get("adset_name", ""),
                "ad_id": row.get("ad_id", ""),
                "ad_name": row.get("ad_name", ""),
                "objective": row.get("objective", ""),
                "spend": spend,
                "impressions": impressions,
                "reach": reach,
                "frequency": to_float(row.get("frequency")),
                "clicks": clicks,
                "inline_link_clicks": inline_link_clicks,
                "ctr": to_float(row.get("ctr")),
                "cpc": to_float(row.get("cpc")),
                "cpm": to_float(row.get("cpm")),
                "purchases": purchases,
                "purchase_value": purchase_value,
                "leads": leads,
            }
        )
    return normalized
