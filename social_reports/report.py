from __future__ import annotations

from typing import Any


def money(value: float, currency: str) -> str:
    return f"{value:,.2f} {currency}"


def number(value: float) -> str:
    return f"{value:,.0f}"


def pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def metric(value: float) -> str:
    return f"{value:,.2f}"


def _rate(value: float) -> str:
    return f"{value * 100:.2f}%"


def _kpi_table(current: dict[str, float], previous: dict[str, float], changes: dict[str, float | None], currency: str) -> str:
    rows = [
        ("Spend", money(current["spend"], currency), money(previous["spend"], currency), pct(changes["spend"])),
        ("Impressions", number(current["impressions"]), number(previous["impressions"]), pct(changes["impressions"])),
        ("Reach", number(current["reach"]), number(previous["reach"]), pct(changes["reach"])),
        ("Clicks", number(current["clicks"]), number(previous["clicks"]), pct(changes["clicks"])),
        ("CTR", f"{current['ctr']:.2f}%", f"{previous['ctr']:.2f}%", pct(changes["ctr"])),
        ("CPC", money(current["cpc"], currency), money(previous["cpc"], currency), pct(changes["cpc"])),
        ("CPM", money(current["cpm"], currency), money(previous["cpm"], currency), pct(changes["cpm"])),
        ("Purchases", number(current["purchases"]), number(previous["purchases"]), pct(changes["purchases"])),
        ("Leads", number(current["leads"]), number(previous["leads"]), pct(changes["leads"])),
        ("Meta ROAS", metric(current["roas_meta"]), metric(previous["roas_meta"]), pct(changes["roas_meta"])),
    ]
    lines = ["| KPI | Current Month | Previous Month | Change |", "| --- | ---: | ---: | ---: |"]
    lines.extend(f"| {name} | {cur} | {prev} | {change} |" for name, cur, prev, change in rows)
    return "\n".join(lines)


def _campaign_rows(campaigns: list[dict[str, Any]], currency: str, limit: int = 10) -> str:
    if not campaigns:
        return "No campaign rows were returned."

    lines = [
        "| Account | Campaign | Objective | Spend | Clicks | CTR | Purchases | Leads | CPA | ROAS |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in campaigns[:limit]:
        conversion_count = item["purchases"] or item["leads"]
        cpa = item["cpa_purchase"] if item["purchases"] else item["cpl"]
        account_name = item.get("account_name") or item.get("account_alias") or item.get("account_id") or "Meta"
        lines.append(
            "| {account} | {campaign} | {objective} | {spend} | {clicks} | {ctr:.2f}% | {purchases} | {leads} | {cpa} | {roas:.2f} |".format(
                account=str(account_name).replace("|", "/"),
                campaign=str(item["campaign_name"]).replace("|", "/"),
                objective=str(item["objective"]).replace("|", "/"),
                spend=money(item["spend"], currency),
                clicks=number(item["clicks"]),
                ctr=item["ctr"],
                purchases=number(item["purchases"]),
                leads=number(item["leads"]),
                cpa=money(cpa, currency) if conversion_count else "n/a",
                roas=item["roas_meta"],
            )
        )
    return "\n".join(lines)


def _organic_rollup_table(rows: list[dict[str, Any]], label_key: str) -> str:
    if not rows:
        return "No organic rows were returned."
    lines = [
        f"| {label_key.replace('_', ' ').title()} | Posts | Views | Reach | Engagements | ER |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {label} | {posts} | {views} | {reach} | {engagements} | {er} |".format(
                label=str(row.get(label_key, "Unknown")).replace("|", "/"),
                posts=number(row.get("posts", 0)),
                views=number(row.get("views", 0)),
                reach=number(row.get("reach", 0)),
                engagements=number(row.get("engagements", 0)),
                er=_rate(float(row.get("engagement_rate") or 0)),
            )
        )
    return "\n".join(lines)


def _organic_top_content(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No organic content rows were returned."
    lines = [
        "| Platform | Format | Topic | Engagements | Views | ER | Content |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows[:10]:
        preview = str(row.get("text_preview") or "").replace("|", "/")
        permalink = str(row.get("permalink") or "")
        content = f"[{preview[:90] or row.get('content_id', 'Open')}]({permalink})" if permalink else preview[:90]
        lines.append(
            "| {platform} | {format} | {topic} | {engagements} | {views} | {er} | {content} |".format(
                platform=str(row.get("platform", "")).title(),
                format=str(row.get("content_format", "")),
                topic=str(row.get("content_topic", "")),
                engagements=number(row.get("engagements", 0)),
                views=number(row.get("views", 0)),
                er=_rate(float(row.get("engagement_rate") or 0)),
                content=content,
            )
        )
    return "\n".join(lines)


def _organic_recommendations(organic: dict[str, Any] | None) -> list[str]:
    if not organic or not organic.get("totals", {}).get("posts"):
        return ["Publish enough organic content during the month to identify repeatable patterns."]

    recommendations = []
    by_format = organic.get("by_format", [])
    by_topic = organic.get("by_topic", [])
    if by_format:
        best_format = by_format[0]
        recommendations.append(
            f"Double down on {best_format['content_format']} content; it produced the strongest organic engagement this month."
        )
    if by_topic:
        best_topic = by_topic[0]
        recommendations.append(
            f"Build next month's content calendar around '{best_topic['content_topic']}' themes first."
        )
    totals = organic.get("totals", {})
    if totals.get("shares", 0) < totals.get("comments", 0):
        recommendations.append("Add more save/share triggers: checklists, before-after proof, comparisons, and practical tips.")
    recommendations.append("Turn the top organic posts into paid creative tests before making brand-new ads.")
    return recommendations


def _organic_section(organic: dict[str, Any] | None) -> str:
    if not organic:
        return """## Organic Content Performance

Organic reporting was not enabled or no organic connector data was available.
"""

    totals = organic.get("totals", {})
    warnings = organic.get("warnings", [])
    warning_lines = "\n".join(f"- {warning}" for warning in warnings[:8]) or "- No organic data warnings."
    recommendation_lines = "\n".join(f"- {item}" for item in _organic_recommendations(organic))

    return f"""## Organic Content Performance

- Published content analyzed: {number(totals.get("posts", 0))}
- Views: {number(totals.get("views", 0))}
- Reach: {number(totals.get("reach", 0))}
- Engagements: {number(totals.get("engagements", 0))}
- Engagement rate by reach: {_rate(float(totals.get("engagement_rate") or 0))}

### Organic by Platform

{_organic_rollup_table(organic.get("by_platform", []), "platform")}

### Content Formats That Worked

{_organic_rollup_table(organic.get("by_format", []), "content_format")}

### Content Themes That Worked

{_organic_rollup_table(organic.get("by_topic", []), "content_topic")}

### Top Organic Content

{_organic_top_content(organic.get("top_content", []))}

### Organic Recommendations

{recommendation_lines}

### Organic Data Notes

{warning_lines}
"""


def _flags(campaigns: list[dict[str, Any]], current: dict[str, float], currency: str) -> list[str]:
    flags = []
    if current["spend"] > 0 and current["purchases"] == 0 and current["leads"] == 0:
        flags.append("Spend was recorded, but no purchases or leads were returned by Meta.")
    if current["ctr"] and current["ctr"] < 1:
        flags.append("Overall CTR is below 1%; review creative hooks, audience fit, and offer clarity.")
    if current["frequency"] > 4:
        flags.append("Frequency is above 4; check creative fatigue and audience saturation.")

    waste = [
        item for item in campaigns
        if item["spend"] > 0 and item["purchases"] == 0 and item["leads"] == 0
    ]
    if waste:
        worst = sorted(waste, key=lambda item: item["spend"], reverse=True)[0]
        flags.append(
            f"Highest no-conversion spend: {worst['campaign_name']} at {money(worst['spend'], currency)}."
        )

    bad_objectives = [
        item for item in campaigns
        if "ENGAGEMENT" in str(item.get("objective", "")).upper()
    ]
    if bad_objectives:
        flags.append("At least one campaign appears to use an engagement objective; verify it is intentional.")

    return flags or ["No critical automated flags were triggered."]


def _conversations_section(conversations: dict[str, Any] | None) -> str:
    if not conversations or not conversations.get("total_conversations"):
        return ""

    total = conversations.get("total_conversations", 0)
    received = conversations.get("messages_received", 0)
    sent = conversations.get("messages_sent", 0)
    rate = conversations.get("response_rate", 0)
    avg_display = conversations.get("avg_response_time_display", "N/A")

    return f"""## Messenger & Conversations

- Total Conversations: {total}
- Messages Received: {received}
- Messages Sent (Replies): {sent}
- Response Rate: {rate:.0f}%
- Average Response Time: {avg_display}
"""


def render_monthly_report(
    *,
    client_name: str,
    client_id: str,
    report_month: str,
    previous_month: str,
    currency: str,
    current: dict[str, float],
    previous: dict[str, float],
    changes: dict[str, float | None],
    campaigns: list[dict[str, Any]],
    organic: dict[str, Any] | None = None,
    conversations: dict[str, Any] | None = None,
) -> str:
    top_by_spend = campaigns
    top_by_conversions = sorted(
        campaigns,
        key=lambda item: (item["purchases"] + item["leads"], item["roas_meta"]),
        reverse=True,
    )
    flags = _flags(campaigns, current, currency)

    return f"""# Monthly Social Media Report - {client_name}

Client ID: `{client_id}`
Report Month: `{report_month}`
Previous Month: `{previous_month}`

## Executive Summary

- Total spend: {money(current["spend"], currency)}
- Clicks: {number(current["clicks"])} at {current["ctr"]:.2f}% CTR
- Purchases: {number(current["purchases"])}
- Leads: {number(current["leads"])}
- Meta-reported ROAS: {current["roas_meta"]:.2f}

## Month-over-Month Performance

{_kpi_table(current, previous, changes, currency)}

{_organic_section(organic)}

{_conversations_section(conversations)}

## Top Campaigns by Spend

{_campaign_rows(top_by_spend, currency)}

## Top Campaigns by Conversions

{_campaign_rows(top_by_conversions, currency)}

## Automated Flags

{chr(10).join(f"- {flag}" for flag in flags)}

## Recommended Next Actions

- Validate that all active conversion campaigns optimize for the correct event.
- Review campaigns with high spend and zero conversions before increasing budget.
- Refresh weak creatives where CTR is low or frequency is high.
- Keep UTM naming consistent so future reports can connect ads to website results.

## Notes

This report uses platform-reported Meta Ads data only. It does not include Shopify,
CRM, call center, or payment-provider validation yet.
"""
