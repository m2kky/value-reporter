from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .metrics import percent_change
from .report import money, number


class AiReportError(RuntimeError):
    pass


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def _rate(value: float) -> str:
    return f"{value * 100:.2f}%"


def _clean_text(value: Any) -> str:
    text = str(value or "")
    markers = ("Ø", "Ù", "ðŸ", "â€", "ï¸")
    if not any(marker in text for marker in markers):
        return text
    try:
        return text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text


def _top(rows: list[dict[str, Any]], key: str, limit: int = 5) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: _float(row.get(key)), reverse=True)[:limit]


def _summary_totals(summary: dict[str, Any] | None) -> dict[str, float]:
    raw = (summary or {}).get("totals") or {}
    return {
        "posts": _float(raw.get("posts")),
        "views": _float(raw.get("views")),
        "reach": _float(raw.get("reach")),
        "engagements": _float(raw.get("engagements")),
        "engagement_rate": _float(raw.get("engagement_rate")),
    }


def _changes(current: dict[str, float], previous: dict[str, float]) -> dict[str, float | None]:
    return {key: percent_change(current.get(key, 0), previous.get(key, 0)) for key in current}


def _output_text(payload: dict[str, Any]) -> str:
    texts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                texts.append(content.get("text", ""))
    return "\n".join(text for text in texts if text).strip()


def ai_enabled() -> bool:
    return os.environ.get("AI_REPORT_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def build_ai_context(
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
    organic_summary: dict[str, Any] | None,
    organic_rows: list[dict[str, Any]],
    organic_previous_summary: dict[str, Any] | None = None,
    organic_previous_rows: list[dict[str, Any]] | None = None,
    conversations: dict[str, Any] | None = None,
    leads: dict[str, Any] | None = None,
) -> dict[str, Any]:
    organic_current_totals = _summary_totals(organic_summary)
    organic_previous_totals = _summary_totals(organic_previous_summary)
    return {
        "client": {"id": client_id, "name": client_name, "currency": currency},
        "period": {"current_month": report_month, "previous_month": previous_month},
        "paid": {
            "current": current,
            "previous": previous,
            "changes_percent": changes,
            "top_campaigns_by_spend": _top(campaigns, "spend", 8),
            "top_campaigns_by_clicks": _top(campaigns, "clicks", 8),
            "top_campaigns_by_roas": _top(campaigns, "roas_meta", 8),
            "campaign_count": len(campaigns),
        },
        "organic": {
            "summary": organic_summary or {},
            "previous_summary": organic_previous_summary or {},
            "changes_percent": _changes(organic_current_totals, organic_previous_totals),
            "top_content": _top(organic_rows, "engagements", 10),
            "previous_top_content": _top(organic_previous_rows or [], "engagements", 10),
            "content_count": len(organic_rows),
            "previous_content_count": len(organic_previous_rows or []),
        },
        "conversations": conversations or {},
        "leads": leads or {},
        "methodology": {
            "ctr": "clicks / impressions * 100",
            "cpc": "spend / clicks",
            "cpm": "spend / impressions * 1000",
            "frequency": "impressions / reach",
            "engagement_rate": "engagements / reach",
            "month_over_month": "(current - previous) / previous * 100",
            "limitations": [
                "Stories are not collected yet because Instagram stories need a separate short-lived polling workflow.",
                "Shopify, CRM, offline sales, and payment-provider validation are not included in this report yet.",
            ],
        },
    }


def _paid_narrative(context: dict[str, Any]) -> str:
    currency = context["client"]["currency"]
    current = context["paid"]["current"]
    previous = context["paid"]["previous"]
    changes = context["paid"]["changes_percent"]
    top_campaigns = context["paid"]["top_campaigns_by_spend"]

    lines = [
        "## أداء الإعلانات المدفوعة",
        "",
        (
            f"الإعلانات المدفوعة قفلت الشهر بإنفاق {money(current.get('spend', 0), currency)}، "
            f"ووصلت إلى {number(current.get('impressions', 0))} ظهور، "
            f"{number(current.get('reach', 0))} وصول، و{number(current.get('clicks', 0))} نقرة. "
            f"معدل النقر CTR كان {current.get('ctr', 0):.2f}%، "
            f"ومتوسط تكلفة النقرة CPC وصل إلى {money(current.get('cpc', 0), currency)}، "
            f"ومتوسط تكلفة الألف ظهور CPM وصل إلى {money(current.get('cpm', 0), currency)}."
        ),
        "",
        "### مقارنة شهرية مع الشهر السابق",
        "",
        "| المؤشر | الشهر الحالي | الشهر السابق | التغيير | طريقة الحساب |",
        "| --- | ---: | ---: | ---: | --- |",
        f"| الإنفاق | {money(current.get('spend', 0), currency)} | {money(previous.get('spend', 0), currency)} | {_pct(changes.get('spend'))} | مجموع الإنفاق من Meta Ads لكل الحسابات المختارة |",
        f"| الظهور | {number(current.get('impressions', 0))} | {number(previous.get('impressions', 0))} | {_pct(changes.get('impressions'))} | مجموع مرات ظهور الإعلانات |",
        f"| الوصول | {number(current.get('reach', 0))} | {number(previous.get('reach', 0))} | {_pct(changes.get('reach'))} | مجموع الوصول المبلغ عنه من Meta |",
        f"| النقرات | {number(current.get('clicks', 0))} | {number(previous.get('clicks', 0))} | {_pct(changes.get('clicks'))} | مجموع النقرات من Meta |",
        f"| CTR | {current.get('ctr', 0):.2f}% | {previous.get('ctr', 0):.2f}% | {_pct(changes.get('ctr'))} | النقرات / الظهور * 100 |",
        f"| CPC | {money(current.get('cpc', 0), currency)} | {money(previous.get('cpc', 0), currency)} | {_pct(changes.get('cpc'))} | الإنفاق / النقرات |",
        f"| CPM | {money(current.get('cpm', 0), currency)} | {money(previous.get('cpm', 0), currency)} | {_pct(changes.get('cpm'))} | الإنفاق / الظهور * 1000 |",
        "",
        "### أفضل الحملات وقراءة القرار",
        "",
    ]

    if top_campaigns:
        lines.extend(
            [
                "| الحملة | الإنفاق | الظهور | النقرات | CTR | CPC | الخلاصة |",
                "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for item in top_campaigns[:6]:
            campaign_name = _clean_text(item.get("campaign_name", "Unknown")).replace("|", "/")
            conversions = _float(item.get("leads")) + _float(item.get("purchases"))
            if conversions:
                conclusion = "تستحق مراجعة أعمق لأن بها إشارات تحويل."
            elif _float(item.get("clicks")):
                conclusion = "تولد اهتماما وزيارات؛ نحتاج ربط أوضح بنتائج التحويل."
            else:
                conclusion = "تحتاج مراجعة الرسالة أو الاستهداف قبل التوسع."
            lines.append(
                f"| {campaign_name} | "
                f"{money(_float(item.get('spend')), currency)} | {number(item.get('impressions', 0))} | "
                f"{number(item.get('clicks', 0))} | {_float(item.get('ctr')):.2f}% | "
                f"{money(_float(item.get('cpc')), currency)} | {conclusion} |"
            )
        lines.append("")
        best = top_campaigns[0]
        best_name = _clean_text(best.get("campaign_name", "Unknown"))
        lines.append(
            f"- أعلى تركيز للميزانية كان على `{best_name}` "
            f"بإنفاق {money(_float(best.get('spend')), currency)}. دي أول حملة نراجعها عند قرار التوسيع أو إعادة الهيكلة."
        )
    else:
        lines.append("- لم ترجع Meta أي صفوف حملات لهذا الشهر، لذلك لا يوجد ترتيب حملات قابل للتحليل.")
    if current.get("spend", 0) and not current.get("leads", 0) and not current.get("purchases", 0):
        lines.append(
            "- يوجد إنفاق ونشاط نقر/تفاعل، لكن لا توجد Leads أو Purchases راجعة من Meta. ده غالبا معناه إن الحملات Awareness/Traffic/Engagement أو إن أحداث التحويل غير موصولة بالكامل في طبقة التقارير."
        )
    if current.get("ctr", 0) > previous.get("ctr", 0):
        lines.append(
            f"- ملاءمة الكريتيف اتحسنت: CTR اتحرك من {previous.get('ctr', 0):.2f}% إلى {current.get('ctr', 0):.2f}%، وده معناه إن الرسالة كانت أقدر على جذب النقرات."
        )
    if current.get("cpm", 0) > previous.get("cpm", 0):
        lines.append(
            f"- تكلفة شراء الظهور زادت: CPM ارتفع {_pct(changes.get('cpm'))}. قرار الميزانية الشهر الجاي لازم يحمي أقوى كريتيفات ويتجنب توسيع الرسائل الضعيفة."
        )
    return "\n".join(lines)


def _organic_narrative(context: dict[str, Any]) -> str:
    organic = context["organic"]
    summary = organic.get("summary") or {}
    previous_summary = organic.get("previous_summary") or {}
    changes = organic.get("changes_percent") or {}
    totals = summary.get("totals") or {}
    previous_totals = previous_summary.get("totals") or {}
    by_format = summary.get("by_format") or []
    by_topic = summary.get("by_topic") or []
    top_content = organic.get("top_content") or []
    previous_top_content = organic.get("previous_top_content") or []
    warnings = summary.get("warnings") or []

    lines = [
        "## أداء المحتوى العضوي",
        "",
        (
            f"تحليل المحتوى العضوي غطى {number(totals.get('posts', 0))} قطعة محتوى، "
            f"وحقق {number(totals.get('views', 0))} مشاهدة/إشارة وصول، "
            f"و{number(totals.get('engagements', 0))} تفاعل إجمالي. "
            f"معدل التفاعل على الوصول كان {_rate(_float(totals.get('engagement_rate')))}."
        ),
        "",
        "### مقارنة العضوي مع الشهر السابق",
        "",
        "| المؤشر | الشهر الحالي | الشهر السابق | التغيير | طريقة الحساب |",
        "| --- | ---: | ---: | ---: | --- |",
        f"| عدد المحتوى | {number(totals.get('posts', 0))} | {number(previous_totals.get('posts', 0))} | {_pct(changes.get('posts'))} | عدد المنشورات/الريلز داخل الفترة |",
        f"| المشاهدات/الوصول | {number(totals.get('views', 0))} | {number(previous_totals.get('views', 0))} | {_pct(changes.get('views'))} | مجموع views أو reach حسب المتاح من المنصة |",
        f"| الوصول | {number(totals.get('reach', 0))} | {number(previous_totals.get('reach', 0))} | {_pct(changes.get('reach'))} | مجموع reach للمنشورات والريلز |",
        f"| التفاعلات | {number(totals.get('engagements', 0))} | {number(previous_totals.get('engagements', 0))} | {_pct(changes.get('engagements'))} | likes + comments + shares + saves حسب المتاح |",
        f"| Engagement Rate | {_rate(_float(totals.get('engagement_rate')))} | {_rate(_float(previous_totals.get('engagement_rate')))} | {_pct(changes.get('engagement_rate'))} | التفاعلات / الوصول |",
        "",
        "### تحليل الفورمات",
        "",
        "| الفورمات | عدد المحتوى | المشاهدات | التفاعلات | ER | الخلاصة |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in by_format[:8]:
        conclusion = "نستمر في الاختبار مع تحسين الهوك."
        if item == by_format[0]:
            conclusion = "الفورمات الأول للتكرار الشهر القادم."
        lines.append(
            f"| {item.get('content_format', 'Unknown')} | {number(item.get('posts', 0))} | {number(item.get('views', 0))} | {number(item.get('engagements', 0))} | {_rate(_float(item.get('engagement_rate')))} | {conclusion} |"
        )

    lines.extend(["", "### تحليل الثيمات", "", "| الثيم | عدد المحتوى | المشاهدات | التفاعلات | ER | الخلاصة |", "| --- | ---: | ---: | ---: | ---: | --- |"])
    for item in by_topic[:8]:
        conclusion = "ثيم مساعد نحتفظ به في الخطة."
        if item == by_topic[0]:
            conclusion = "أقوى ثيم؛ نبني عليه محتوى أكثر."
        lines.append(
            f"| {item.get('content_topic', 'Unknown')} | {number(item.get('posts', 0))} | {number(item.get('views', 0))} | {number(item.get('engagements', 0))} | {_rate(_float(item.get('engagement_rate')))} | {conclusion} |"
        )

    lines.extend(["", "### أفضل محتوى نعيد استخدامه", ""])
    if not top_content:
        lines.append("- لا توجد صفوف محتوى عضوي متاحة لهذا الشهر.")
    for item in top_content[:5]:
        link = item.get("permalink") or ""
        title = _clean_text(item.get("text_preview") or item.get("content_id") or "Open content").strip()
        label = f"[{title[:90]}]({link})" if link else title[:90]
        lines.append(
            f"- {label}: {item.get('content_format', 'Unknown')} / {item.get('content_topic', 'General')} "
            f"حقق {number(item.get('views', 0))} مشاهدة و{number(item.get('engagements', 0))} تفاعل."
        )
    if previous_top_content:
        lines.extend(["", "### مرجع من الشهر السابق", ""])
        for item in previous_top_content[:3]:
            title = _clean_text(item.get("text_preview") or item.get("content_id") or "Open content").strip()
            lines.append(
                f"- الشهر السابق كان من أقوى المحتوى: {title[:90]} "
                f"بـ {number(item.get('engagements', 0))} تفاعل."
            )
    lines.extend(
        [
            "",
            "### ملاحظات البيانات العضوية",
            "",
            "- الاستوريز غير مضافة في هذا الإصدار لأنها تحتاج خطوة polling منفصلة قبل انتهاء صلاحية الستوري.",
        ]
    )
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings[:5])
    return "\n".join(lines)


def deterministic_ai_report(context: dict[str, Any]) -> str:
    client = context["client"]
    period = context["period"]
    current = context["paid"]["current"]
    changes = context["paid"]["changes_percent"]
    currency = client["currency"]
    organic_totals = (context["organic"].get("summary") or {}).get("totals", {})

    headline = (
        f"{client['name']} حقق خلال {period['current_month']} إجمالي "
        f"{number(current.get('impressions', 0))} ظهور مدفوع، "
        f"{number(current.get('clicks', 0))} نقرة، "
        f"و{number(organic_totals.get('engagements', 0))} تفاعل عضوي."
    )

    sections = [
        f"# تقرير الأداء الشهري المدعوم بالذكاء الاصطناعي - {client['name']}",
        "",
        f"شهر التقرير: `{period['current_month']}`",
        f"شهر المقارنة: `{period['previous_month']}`",
        "",
        "## الملخص التنفيذي",
        "",
        headline,
        "",
        (
            f"القراءة الأهم ليست حجم الأرقام فقط، لكن العلاقة بين تكلفة الظهور، استجابة الجمهور للنقر، "
            f"ونوعية المحتوى العضوي التي كسبت الانتباه. الإنفاق تغير {_pct(changes.get('spend'))} عن الشهر السابق، "
            f"بينما CTR تغير {_pct(changes.get('ctr'))}."
        ),
        "",
        "### نقاط الإدارة السريعة",
        "",
        f"- الاستثمار الإعلاني وصل إلى {money(current.get('spend', 0), currency)}، وده يبني قاعدة ظهور واضحة للشهر.",
        f"- CTR عند {current.get('ctr', 0):.2f}% هو مؤشر مباشر على قوة الرسالة والكريتيف مع الجمهور.",
        "- أفضل محتوى عضوي لا يتم التعامل معه كمنشور وانتهى؛ يتم تحويله لاختبارات إعلانية مدفوعة.",
        "- لو Leads أو Purchases متوقعة ومش ظاهرة، يبقى لازم مراجعة أحداث التحويل والـ tracking قبل أي قرار توسع.",
        "",
        _paid_narrative(context),
        "",
        _organic_narrative(context),
        "",
        "## كيف وصلنا للأرقام",
        "",
        "- بيانات الإعلانات المدفوعة تأتي من Meta Ads Insights للحسابات الإعلانية المختارة في الداشبورد.",
        "- بيانات العضوي تأتي من Facebook Page وInstagram Business/Creator account عند توفر الربط والصلاحيات.",
        "- أرقام الشهر الحالي هي مجموع البيانات داخل شهر التقرير فقط.",
        "- أرقام الشهر السابق تستخدم نفس تعريفات المؤشرات للفترة التقويمية السابقة مباشرة.",
        "- التغيير الشهري يتم حسابه بهذه المعادلة: `(الشهر الحالي - الشهر السابق) / الشهر السابق * 100`.",
        "- CTR = النقرات / الظهور * 100.",
        "- CPC = الإنفاق / النقرات.",
        "- CPM = الإنفاق / الظهور * 1000.",
        "- Engagement Rate = التفاعلات / الوصول عند توفر الوصول.",
        "",
        "## الخلاصة الاستراتيجية",
        "",
        (
            "الشهر القادم يجب أن يركز على تحويل إشارات العضوي الناجحة إلى اختبارات مدفوعة، "
            "وحماية الحملات ذات CTR الصحي، وربط التحويلات بشكل أدق حتى ينتقل التقرير من تحليل نشاط "
            "إلى تحليل جودة Leads أو مبيعات."
        ),
        "",
        "## خطة عمل الشهر القادم",
        "",
        "1. تحويل أفضل 3 قطع محتوى عضوي إلى نسخ كريتيف مدفوعة.",
        "2. مراجعة الحملات ذات الإنفاق العالي بدون أحداث تحويل قبل زيادة الميزانية.",
        "3. تحديث hooks للحملات التي زاد فيها CPM بدون تحسن كاف في CTR.",
        "4. تأكيد أحداث التحويل، lead forms، أو CRM mapping حتى لا يظل التقرير محصورا في traffic وengagement.",
        "5. تثبيت naming وtaxonomy للحملات والثيمات حتى تبقى المقارنات الشهرية دقيقة.",
    ]
    return "\n".join(sections) + "\n"


import aiohttp
import asyncio

async def generate_with_openai(prompt_text: str, data_context: dict[str, Any], system_prompt: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise AiReportError("OPENAI_API_KEY is missing.")

    model = os.environ.get("OPENAI_MODEL", "gpt-4o").strip()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{prompt_text}\n\nData Context:\n{json.dumps(data_context, ensure_ascii=False)}"}
    ]

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": 4000,
        "temperature": 0.7,
    }

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions").strip()

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                base_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "monthly-social-report/0.1",
                    "HTTP-Referer": "https://github.com/", # Optional for OpenRouter
                    "X-Title": "Social Reports Pipeline", # Optional for OpenRouter
                },
                json=body,
                timeout=180
            ) as response:
                if not response.ok:
                    detail = await response.text()
                    raise AiReportError(f"OpenAI API HTTP {response.status}: {detail}")
                payload = await response.json()
        except aiohttp.ClientError as error:
            raise AiReportError(f"OpenAI API network error: {error}")

    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise AiReportError(f"OpenAI API returned unexpected format: {e}")
    
    if not text:
        raise AiReportError("OpenAI API returned no output text.")
    return text


def _build_system_prompt(language: str) -> str:
    if language == "en":
        return "You are a senior performance marketing strategist. Reply in professional English. Be concise, actionable, and data-driven. Use Markdown formatting."
    return "You are a senior performance marketing strategist analyzing data for an Egyptian agency. Reply in professional Arabic. Be concise, actionable, and data-driven. Use Markdown formatting."


def _build_template_prompt(template: str, language: str, kpi_targets: list[dict] | None, custom_prompt: str) -> str:
    lang_note = "Reply in English." if language == "en" else "Reply in Arabic."

    if template == "content":
        return f"""Analyze the organic content performance data in depth. {lang_note}
Focus on:
- Top performing content formats (VIDEO, IMAGE, CAROUSEL, REEL)
- Best content themes/topics and what made them work
- Engagement rate analysis and what drives it
- Recommendations for next month's content calendar
Use Markdown headings and tables."""

    if template == "conversations":
        return f"""Analyze the messaging and conversations data. {lang_note}
Focus on:
- Total conversation volume and trends
- Response rate and average response time
- Quality of customer service based on the numbers
- Recommendations to improve response times and rates
Use Markdown headings and tables."""

    if template == "kpi" and kpi_targets:
        targets_text = "\n".join(
            f"- {t.get('label', t.get('metric', ''))}: Target = {t.get('target', 'N/A')}"
            for t in kpi_targets
        )
        return f"""Compare the actual performance data against the following KPI targets. {lang_note}
        
KPI Targets set by the user:
{targets_text}

For each KPI:
1. Show the target vs actual value
2. Calculate achievement percentage
3. Analyze why targets were met or missed
4. Provide recommendations to improve underperforming KPIs

Use a Markdown table for the comparison and add analysis sections after."""

    if template == "custom" and custom_prompt:
        return f"""{custom_prompt}

{lang_note}
Use Markdown formatting with headings, tables, and bullet points."""

    # Default: full analysis
    if language == "en":
        return """Write a comprehensive Monthly Performance Report covering:
# Monthly Performance Summary
## Key Highlights (top 3-4 KPIs)
## Paid Ads & Lead Generation (what worked, what didn't, leads/CPL analysis)
## Organic Content Deep Dive (top themes, formats, and summarize the top comments/sentiment)
## Content Attribution (analyze which content formats drove the most messages or leads)
## Inbox & Customer Service (analyze conversation volumes, extract FAQs from transcripts, and evaluate moderator response quality)
## Action Plan & Recommendations (3-5 concrete next steps)
Use Markdown tables for data comparisons."""
    else:
        return """Write a comprehensive, extremely detailed Executive Summary in Arabic.
Use this exact Markdown structure:
# ملخص الأداء الشهري
## أبرز الأرقام
(Highlight the top 3-4 KPIs overall)
## تحليل الحملات المدفوعة وإعلانات الـ Leads
(Summarize what worked and what didn't in paid ads, analyze lead forms, and cost per lead)
## تحليل المحتوى المجاني والتعليقات
(Summarize the top performing organic themes and formats. Read the 'top_comments' provided in the data and summarize the sentiment and what users are saying)
## تأثير المحتوى على المبيعات (Content Attribution)
(Analyze which content formats or topics likely drove the most messages, bookings, or leads)
## جودة خدمة العملاء والرسائل
(Analyze conversation volumes. Read the 'transcripts' of conversations from Facebook, Instagram, and WhatsApp. Extract the Frequently Asked Questions (FAQs). Evaluate the quality of the moderator's responses)
## خطة العمل والتوصيات
(Provide 3-5 concrete, actionable steps for next month)"""


async def template_ai_pipeline(context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    ai_options = context.get("ai_options", {})
    template = ai_options.get("template", "full")
    language = ai_options.get("language", "ar")
    kpi_targets = context.get("kpi_targets")
    custom_prompt = ai_options.get("custom_prompt", "")

    system_prompt = _build_system_prompt(language)
    user_prompt = _build_template_prompt(template, language, kpi_targets, custom_prompt)

    # Build focused data context based on template
    data_for_ai = {
        "client": context.get("client", {}),
        "period": context.get("period", {}),
    }

    if template in ("full", "kpi", "custom"):
        data_for_ai["paid"] = context.get("paid", {})
        data_for_ai["organic"] = context.get("organic", {})
        data_for_ai["conversations"] = context.get("conversations", {})
    elif template == "content":
        data_for_ai["organic"] = context.get("organic", {})
    elif template == "conversations":
        data_for_ai["conversations"] = context.get("conversations", {})

    if kpi_targets:
        data_for_ai["kpi_targets"] = kpi_targets

    report_text = await generate_with_openai(user_prompt, data_for_ai, system_prompt)

    # Generate slides JSON
    lang_note = "in English" if language == "en" else "in Arabic"
    json_prompt = f"""Take the following report and structure it into a strict JSON array of slides {lang_note}.
Format:
{{
  "slides": [
    {{ "type": "title", "title": "...", "subtitle": "..." }},
    {{ "type": "summary", "title": "...", "bullets": ["...", "..."] }},
    {{ "type": "data", "title": "...", "insights": ["..."] }},
    {{ "type": "action", "title": "...", "bullets": ["..."] }}
  ]
}}
Return ONLY valid JSON."""

    try:
        slides_json_str = await generate_with_openai(json_prompt, {"report": report_text}, system_prompt)
        slides_json_str = slides_json_str.strip()
        if slides_json_str.startswith("```json"):
            slides_json_str = slides_json_str[7:]
        if slides_json_str.startswith("```"):
            slides_json_str = slides_json_str[3:]
        if slides_json_str.endswith("```"):
            slides_json_str = slides_json_str[:-3]
        slides_data = json.loads(slides_json_str.strip())
    except (json.JSONDecodeError, AiReportError):
        slides_data = {"slides": [{"type": "error", "title": "Failed to parse slides JSON"}]}

    return report_text, slides_data


async def write_ai_report(path: Path, context: dict[str, Any]) -> dict[str, Any]:
    mode = "local"
    error = ""
    report = ""
    slides_data = None
    
    if ai_enabled():
        try:
            report, slides_data = await template_ai_pipeline(context)
            mode = "openai"
        except AiReportError as exc:
            error = str(exc)
            report = deterministic_ai_report(context)
    else:
        report = deterministic_ai_report(context)

    if mode == "local":
        report += (
            "\n---\n"
            "ملاحظة التوليد: هذا التقرير تم توليده محليا بقواعد تحليل ثابتة، بدون إرسال بيانات العميل لأي API خارجي. "
            "لتوليد صياغة أكثر مرونة باستخدام OpenAI اضبط `AI_REPORT_ENABLED=true` و`OPENAI_API_KEY`.\n"
        )
    if error:
        report += f"\nسبب الرجوع للنسخة المحلية من OpenAI: `{error}`\n"

    path.write_text(report, encoding="utf-8")
    
    if slides_data:
        slides_path = path.parent / "slides.json"
        with slides_path.open("w", encoding="utf-8") as f:
            json.dump(slides_data, f, ensure_ascii=False, indent=2)

    return {"mode": mode, "error": error, "path": str(path), "slides_generated": bool(slides_data)}

