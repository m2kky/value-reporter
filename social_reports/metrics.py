from __future__ import annotations

from collections import defaultdict
from typing import Any


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def percent_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals = {
        "spend": 0.0,
        "impressions": 0.0,
        "reach": 0.0,
        "clicks": 0.0,
        "inline_link_clicks": 0.0,
        "purchases": 0.0,
        "purchase_value": 0.0,
        "leads": 0.0,
    }
    for row in rows:
        for key in totals:
            totals[key] += float(row.get(key) or 0)

    totals["ctr"] = safe_div(totals["clicks"], totals["impressions"]) * 100
    totals["cpc"] = safe_div(totals["spend"], totals["clicks"])
    totals["cpm"] = safe_div(totals["spend"], totals["impressions"]) * 1000
    totals["frequency"] = safe_div(totals["impressions"], totals["reach"])
    totals["cpa_purchase"] = safe_div(totals["spend"], totals["purchases"])
    totals["cpl"] = safe_div(totals["spend"], totals["leads"])
    totals["roas_meta"] = safe_div(totals["purchase_value"], totals["spend"])
    return totals


def compare(current: dict[str, float], previous: dict[str, float]) -> dict[str, float | None]:
    keys = [
        "spend",
        "impressions",
        "reach",
        "clicks",
        "inline_link_clicks",
        "purchases",
        "purchase_value",
        "leads",
        "ctr",
        "cpc",
        "cpm",
        "cpa_purchase",
        "cpl",
        "roas_meta",
    ]
    return {key: percent_change(current.get(key, 0), previous.get(key, 0)) for key in keys}


def campaign_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "account_alias": "",
            "account_id": "",
            "account_name": "",
            "campaign_id": "",
            "campaign_name": "",
            "objective": "",
            "spend": 0.0,
            "impressions": 0.0,
            "clicks": 0.0,
            "inline_link_clicks": 0.0,
            "purchases": 0.0,
            "purchase_value": 0.0,
            "leads": 0.0,
        }
    )

    for row in rows:
        key = "|".join(
            [
                str(row.get("account_id") or row.get("account_alias") or "unknown_account"),
                str(row.get("campaign_id") or row.get("campaign_name") or "unknown_campaign"),
            ]
        )
        bucket = grouped[str(key)]
        bucket["account_alias"] = row.get("account_alias", "")
        bucket["account_id"] = row.get("account_id", "")
        bucket["account_name"] = row.get("account_name", "")
        bucket["campaign_id"] = row.get("campaign_id", "")
        bucket["campaign_name"] = row.get("campaign_name", "Unknown")
        bucket["objective"] = row.get("objective", "")
        for metric in [
            "spend",
            "impressions",
            "clicks",
            "inline_link_clicks",
            "purchases",
            "purchase_value",
            "leads",
        ]:
            bucket[metric] += float(row.get(metric) or 0)

    campaigns = []
    for bucket in grouped.values():
        bucket["ctr"] = safe_div(bucket["clicks"], bucket["impressions"]) * 100
        bucket["cpc"] = safe_div(bucket["spend"], bucket["clicks"])
        bucket["cpm"] = safe_div(bucket["spend"], bucket["impressions"]) * 1000
        bucket["cpa_purchase"] = safe_div(bucket["spend"], bucket["purchases"])
        bucket["cpl"] = safe_div(bucket["spend"], bucket["leads"])
        bucket["roas_meta"] = safe_div(bucket["purchase_value"], bucket["spend"])
        campaigns.append(bucket)

    return sorted(campaigns, key=lambda item: item["spend"], reverse=True)
