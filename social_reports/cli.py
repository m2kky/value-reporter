from __future__ import annotations

import argparse
import json
import logging
import sys
import asyncio
from pathlib import Path

from .ai_report import build_ai_context, write_ai_report
from .config import ConfigError, MetaAccountConfig, get_client, load_config
from .date_windows import DateWindowError, resolve_month
from .meta_client import MetaApiError, MetaClient
from .metrics import aggregate, campaign_table, compare
from .normalize import normalize_meta_rows
from .organic import fetch_organic_content
from .organic_analysis import summarize_organic
from .report import render_monthly_report
from .storage import ensure_run_dirs, write_csv, write_json

logger = logging.getLogger(__name__)


def update_status(dirs: dict[str, Path], step: int, message: str) -> None:
    """Write pipeline progress to pipeline_status.json for real-time UI tracking."""
    status_path = dirs["root"] / "pipeline_status.json"
    try:
        status_path.write_text(
            json.dumps({"ok": True, "step": step, "message": message}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass  # Don't let status tracking break the pipeline

class PipelineError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate monthly social media reports.")
    parser.add_argument("--client", required=True, help="Client ID from clients.json")
    parser.add_argument("--month", help="Report month in YYYY-MM format. Defaults to last completed month.")
    parser.add_argument("--since", help="Start date in YYYY-MM-DD format (overrides --month)")
    parser.add_argument("--until", help="End date in YYYY-MM-DD format (overrides --month)")
    parser.add_argument("--config", help="Path to clients.json")
    parser.add_argument("--env", default=".env", help="Path to .env file")
    parser.add_argument("--dry-run", action="store_true", help="Validate config without calling APIs")
    return parser.parse_args()


def setup_logging(debug: bool = False, log_file: str | None = None) -> None:
    level = logging.DEBUG if debug else logging.INFO
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def safe_slug(value: str) -> str:
    cleaned = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            cleaned.append(char)
        else:
            cleaned.append("_")
    return "".join(cleaned).strip("_") or "account"


def require_meta_accounts(client_id: str, accounts: list[MetaAccountConfig]) -> None:
    missing = []
    if not accounts:
        missing.append("no Meta ad accounts configured")

    for account in accounts:
        if not account.access_token or account.access_token.startswith("replace_with"):
            missing.append(f"{account.id}: Meta access token ({account.access_token_env})")
        if not account.ad_account_id or account.ad_account_id.startswith("act_123456"):
            missing.append(f"{account.id}: Meta ad account ID ({account.ad_account_id_env})")

    if missing:
        raise PipelineError(
            f"{client_id}: missing {', '.join(missing)}. Fill .env before running the API pipeline."
        )


async def run() -> int:
    args = parse_args()
    config = load_config(args.config, args.env)
    client = get_client(config, args.client)
    
    from .date_windows import resolve_date_range, resolve_month
    if args.since and args.until:
        window = resolve_date_range(args.since, args.until, client.timezone)
    else:
        window = resolve_month(args.month, client.timezone)
        
    output_folder = client.output_folder or client.id
    output_root = config.output_dir / output_folder / window.label

    # Setup basic console logging early
    setup_logging()

    if args.dry_run:
        logger.info(f"Client: {client.name} ({client.id})")
        logger.info(f"Report period: {window.label} ({window.start} to {window.end})")
        logger.info(f"Previous period: {window.previous_label} ({window.previous_start} to {window.previous_end})")
        logger.info(f"Output: {output_root}")
        logger.info(f"Meta enabled: {client.meta.enabled}")
        logger.info(f"Meta API version: {client.meta.api_version}")
        logger.info(f"Meta levels: {', '.join(client.meta.levels)}")
        for account in client.meta.accounts:
            token_state = "token ok" if account.access_token else f"missing {account.access_token_env}"
            account_state = "ad account ok" if account.ad_account_id else f"missing {account.ad_account_id_env}"
            logger.info(f"Meta account: {account.id} ({account.name}) - {token_state}, {account_state}")
        organic_token_state = "token ok" if client.organic.access_token else f"missing {client.organic.access_token_env}"
        organic_page_state = "page ok" if client.organic.page_id else f"missing {client.organic.page_id_env}"
        logger.info(f"Organic enabled: {client.organic.enabled} - {organic_token_state}, {organic_page_state}")
        ig_token_state = "token ok" if client.organic.instagram_access_token else f"missing {client.organic.instagram_access_token_env}"
        ig_id_state = "ig id ok" if client.organic.instagram_account_id else f"optional {client.organic.instagram_account_id_env}"
        logger.info(f"Instagram organic: {ig_token_state}, {ig_id_state}")
        return 0

    if not client.meta.enabled and not client.organic.enabled:
        raise PipelineError(f"{client.id}: no enabled platform connectors found (enable Meta Ads or Organic).")

    if client.meta.enabled:
        require_meta_accounts(client.id, client.meta.accounts)
    dirs = ensure_run_dirs(config.output_dir, output_folder, window.label)

    # Re-setup logging to also write to the output directory
    setup_logging(log_file=str(dirs["root"] / "pipeline.log"))
    logger.info(f"Starting pipeline for {client.name} - {window.label}")

    account_fields = [
        "account_id",
        "account_name",
        "spend",
        "impressions",
        "reach",
        "frequency",
        "clicks",
        "inline_link_clicks",
        "ctr",
        "cpc",
        "cpm",
        "actions",
        "action_values",
        "date_start",
        "date_stop",
    ]

    current_summary = []
    previous_summary = []
    campaign_daily = []

    if not client.meta.enabled:
        logger.info("Meta Ads disabled, skipping paid data fetch.")

    for account in (client.meta.accounts if client.meta.enabled else []):
        account_slug = safe_slug(account.id)
        meta = MetaClient(
            access_token=account.access_token,
            ad_account_id=account.ad_account_id,
            api_version=client.meta.api_version,
        )

        try:
            logger.info(f"Fetching Meta insights for account {account.id} (current month)")
            update_status(dirs, 2, f"Fetching Paid Data ({account.name or account.id})...")
            current_summary_raw, previous_summary_raw, campaign_daily_raw = await asyncio.gather(
                meta.fetch_insights(since=window.start, until=window.end, fields=account_fields),
                meta.fetch_insights(since=window.previous_start, until=window.previous_end, fields=account_fields),
                meta.fetch_insights(since=window.start, until=window.end, fields=client.meta.fields, level="campaign", time_increment=1)
            )
        except MetaApiError as error:
            logger.error(f"Meta API Error: {client.id}/{account.id}: {error}")
            raise MetaApiError(f"{client.id}/{account.id}: {error}") from error

        write_json(dirs["raw"] / f"meta_{account_slug}_account_summary_current.json", current_summary_raw)
        write_json(dirs["raw"] / f"meta_{account_slug}_account_summary_previous.json", previous_summary_raw)
        write_json(dirs["raw"] / f"meta_{account_slug}_campaign_daily_current.json", campaign_daily_raw)

        current_summary.extend(
            normalize_meta_rows(
                current_summary_raw,
                client_id=client.id,
                report_month=window.label,
                level="account",
                account_alias=account.name,
            )
        )
        previous_summary.extend(
            normalize_meta_rows(
                previous_summary_raw,
                client_id=client.id,
                report_month=window.previous_label,
                level="account",
                account_alias=account.name,
            )
        )
        campaign_daily.extend(
            normalize_meta_rows(
                campaign_daily_raw,
                client_id=client.id,
                report_month=window.label,
                level="campaign",
                account_alias=account.name,
            )
        )

    write_csv(dirs["processed"] / "meta_account_summary_current.csv", current_summary)
    write_csv(dirs["processed"] / "meta_account_summary_previous.csv", previous_summary)
    write_csv(dirs["processed"] / "meta_campaign_daily_current.csv", campaign_daily)

    current_kpis = aggregate(current_summary or campaign_daily)
    previous_kpis = aggregate(previous_summary)
    changes = compare(current_kpis, previous_kpis)
    campaigns = campaign_table(campaign_daily)

    write_json(
        dirs["processed"] / "monthly_kpis.json",
        {
            "current": current_kpis,
            "previous": previous_kpis,
            "changes_percent": changes,
            "campaigns": campaigns,
        },
    )

    organic_summary = None
    organic_previous_summary = None
    organic_rows = []
    organic_previous_rows = []
    conversations = None
    if client.organic.enabled:
        logger.info(f"Fetching organic content for {client.name} (current & previous months)")
        update_status(dirs, 3, "Fetching Organic Media & Insights...")
        (organic_rows, organic_diagnostics), (organic_previous_rows, organic_previous_diagnostics) = await asyncio.gather(
            fetch_organic_content(client.organic, api_version=client.meta.api_version, since=window.start, until=window.end),
            fetch_organic_content(client.organic, api_version=client.meta.api_version, since=window.previous_start, until=window.previous_end)
        )

        organic_summary = summarize_organic(
            organic_rows,
            warnings=organic_diagnostics.get("warnings", []),
        )
        organic_previous_summary = summarize_organic(
            organic_previous_rows,
            warnings=organic_previous_diagnostics.get("warnings", []),
        )
        write_json(dirs["raw"] / "organic_diagnostics.json", organic_diagnostics)
        write_json(dirs["raw"] / "organic_diagnostics_previous.json", organic_previous_diagnostics)
        write_csv(dirs["processed"] / "organic_content.csv", organic_rows)
        write_csv(dirs["processed"] / "organic_content_previous.csv", organic_previous_rows)
        write_json(dirs["processed"] / "organic_summary.json", organic_summary)
        write_json(dirs["processed"] / "organic_summary_previous.json", organic_previous_summary)
        
        # Conversations Step
        logger.info(f"Fetching conversations for {client.name}")
        from .conversations import fetch_conversations
        conversations = await fetch_conversations(
            client.organic,
            api_version=client.meta.api_version,
            since=window.start,
            until=window.end,
        )
        write_json(dirs["processed"] / "conversations.json", conversations)

    logger.info("Rendering markdown report")
    update_status(dirs, 4, "Generating Reports and synthesizing metrics...")
    report = render_monthly_report(
        client_name=client.name,
        client_id=client.id,
        report_month=window.label,
        previous_month=window.previous_label,
        currency=client.currency,
        current=current_kpis,
        previous=previous_kpis,
        changes=changes,
        campaigns=campaigns,
        organic=organic_summary,
        conversations=conversations,
    )
    report_path = dirs["root"] / "monthly_social_report.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info(f"Report generated: {report_path}")

    logger.info("Building AI context")
    update_status(dirs, 5, "Connecting to AI Provider for narrative synthesis. This takes a moment...")
    ai_context = build_ai_context(
        client_name=client.name,
        client_id=client.id,
        report_month=window.label,
        previous_month=window.previous_label,
        currency=client.currency,
        current=current_kpis,
        previous=previous_kpis,
        changes=changes,
        campaigns=campaigns,
        organic_summary=organic_summary,
        organic_previous_summary=organic_previous_summary,
        organic_rows=organic_rows,
        organic_previous_rows=organic_previous_rows,
        conversations=conversations,
    )
    logger.info("Writing AI report")
    # write_ai_report now needs to be async too
    ai_report_status = await write_ai_report(dirs["root"] / "ai_monthly_report.md", ai_context)
    write_json(dirs["processed"] / "ai_report_context.json", ai_context)
    write_json(dirs["processed"] / "ai_report_status.json", ai_report_status)
    logger.info(f"AI report generated: {ai_report_status['path']} ({ai_report_status['mode']})")
    
    update_status(dirs, 6, "Pipeline Completed Successfully! Review your report and export PPTX/PDF when ready.")
    return 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        raise SystemExit(asyncio.run(run()))
    except (ConfigError, DateWindowError, PipelineError, MetaApiError) as error:
        logging.error(f"Error: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

