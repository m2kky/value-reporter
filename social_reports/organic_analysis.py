from __future__ import annotations

from collections import defaultdict
from typing import Any


def _metric_sum(rows: list[dict[str, Any]], key: str) -> float:
    return sum(float(row.get(key) or 0) for row in rows)


def _rollup(rows: list[dict[str, Any]], group_key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            group_key: "",
            "posts": 0,
            "views": 0.0,
            "reach": 0.0,
            "likes": 0.0,
            "comments": 0.0,
            "shares": 0.0,
            "saves": 0.0,
            "engagements": 0.0,
        }
    )
    for row in rows:
        key = str(row.get(group_key) or "Unknown")
        bucket = grouped[key]
        bucket[group_key] = key
        bucket["posts"] += 1
        for metric in ["views", "reach", "likes", "comments", "shares", "saves", "engagements"]:
            bucket[metric] += float(row.get(metric) or 0)

    results = []
    for bucket in grouped.values():
        bucket["engagement_rate"] = (
            bucket["engagements"] / bucket["reach"] if bucket["reach"] else 0.0
        )
        bucket["avg_engagements"] = bucket["engagements"] / bucket["posts"] if bucket["posts"] else 0.0
        results.append(bucket)
    return sorted(results, key=lambda item: (item["engagements"], item["views"]), reverse=True)


def _totals_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a totals dict for a subset of rows."""
    total_posts = len(rows)
    totals = {
        "posts": total_posts,
        "views": _metric_sum(rows, "views"),
        "reach": _metric_sum(rows, "reach"),
        "likes": _metric_sum(rows, "likes"),
        "comments": _metric_sum(rows, "comments"),
        "shares": _metric_sum(rows, "shares"),
        "saves": _metric_sum(rows, "saves"),
        "engagements": _metric_sum(rows, "engagements"),
    }
    reach = totals["reach"]
    totals["engagement_rate"] = totals["engagements"] / reach if reach else 0.0
    return totals


def _platform_detail(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a detailed breakdown for a single platform's rows."""
    return {
        "totals": _totals_for(rows),
        "by_format": _rollup(rows, "content_format"),
        "by_topic": _rollup(rows, "content_topic"),
        "top_content": sorted(
            rows,
            key=lambda row: (float(row.get("engagements") or 0), float(row.get("views") or 0)),
            reverse=True,
        )[:10],
    }


def summarize_organic(rows: list[dict[str, Any]], warnings: list[str] | None = None) -> dict[str, Any]:
    total_posts = len(rows)

    # Split rows by platform
    fb_rows = [r for r in rows if r.get("platform") == "facebook"]
    ig_rows = [r for r in rows if r.get("platform") == "instagram"]
    tiktok_rows = [r for r in rows if r.get("platform") == "TikTok"]
    threads_rows = [r for r in rows if r.get("platform") == "threads"]
    stories_rows = [r for r in rows if r.get("platform") == "instagram_stories"]

    summary = {
        "enabled": True,
        "warnings": warnings or [],
        "totals": _totals_for(rows),
        "by_platform": _rollup(rows, "platform"),
        "by_format": _rollup(rows, "content_format"),
        "by_topic": _rollup(rows, "content_topic"),
        "top_content": sorted(
            rows,
            key=lambda row: (float(row.get("engagements") or 0), float(row.get("views") or 0)),
            reverse=True,
        )[:10],
        # === Per-Platform Detailed Breakdowns ===
        "facebook": _platform_detail(fb_rows) if fb_rows else {"totals": _totals_for([])},
        "instagram": _platform_detail(ig_rows) if ig_rows else {"totals": _totals_for([])},
        "tiktok": _platform_detail(tiktok_rows) if tiktok_rows else {"totals": _totals_for([])},
        "threads": _platform_detail(threads_rows) if threads_rows else {"totals": _totals_for([])},
        "stories": {
            "available": len(stories_rows) > 0,
            "totals": _totals_for(stories_rows),
            "items": sorted(
                stories_rows,
                key=lambda r: (float(r.get("views") or 0)),
                reverse=True,
            )[:10] if stories_rows else [],
        },
    }
    return summary

