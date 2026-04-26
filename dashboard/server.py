from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import traceback
import asyncio
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from social_reports.config import (  # noqa: E402
    DEFAULT_FACEBOOK_POST_INSIGHT_METRICS,
    DEFAULT_INSTAGRAM_MEDIA_INSIGHT_METRICS,
    DEFAULT_META_FIELDS,
    load_config,
    load_dotenv,
    safe_folder_name,
)
from social_reports.graph_client import GraphApiError, GraphClient  # noqa: E402


CONFIG_PATH = ROOT / "clients.json"
ENV_PATH = ROOT / ".env"
STATIC_DIR = ROOT / "dashboard" / "static"

REQUIRED_META_FIELDS = [
    "account_id",
    "account_name",
    "campaign_id",
    "campaign_name",
    "objective",
    "date_start",
    "date_stop",
]

PAID_METRIC_OPTIONS = [
    {"id": "spend", "label": "Spend"},
    {"id": "impressions", "label": "Impressions"},
    {"id": "reach", "label": "Reach"},
    {"id": "frequency", "label": "Frequency"},
    {"id": "clicks", "label": "Clicks"},
    {"id": "inline_link_clicks", "label": "Link Clicks"},
    {"id": "ctr", "label": "CTR"},
    {"id": "cpc", "label": "CPC"},
    {"id": "cpm", "label": "CPM"},
    {"id": "cpp", "label": "CPP"},
    {"id": "actions", "label": "Actions"},
    {"id": "action_values", "label": "Action Values"},
]

FACEBOOK_ORGANIC_METRIC_OPTIONS = [
    {"id": "post_impressions_unique", "label": "Post Reach"},
    {"id": "post_clicks", "label": "Post Clicks"},
]

INSTAGRAM_ORGANIC_METRIC_OPTIONS = [
    {"id": "views", "label": "Views"},
    {"id": "reach", "label": "Reach"},
    {"id": "likes", "label": "Likes"},
    {"id": "comments", "label": "Comments"},
    {"id": "shares", "label": "Shares"},
    {"id": "saved", "label": "Saves"},
    {"id": "total_interactions", "label": "Total Interactions"},
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_env() -> None:
    load_dotenv(ENV_PATH)


def unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def slug(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif char in {" ", "-", "_"}:
            cleaned.append("_")
    return "_".join(part for part in "".join(cleaned).split("_") if part) or "asset"


def output_folder_from_client(client: dict[str, Any]) -> str:
    return safe_folder_name(client.get("output_folder", "") or client.get("id", "client"))


def output_root_for_client(client_id: str, period: str) -> Path:
    data = read_json(CONFIG_PATH)
    client = find_client(data, client_id)
    folder = output_folder_from_client(client)
    root = ROOT / "outputs" / folder / period
    legacy_root = ROOT / "outputs" / client_id / period
    if root.exists() or not legacy_root.exists():
        return root
    return legacy_root


def page_name_from_assets(page_id: str) -> str:
    if not page_id:
        return ""
    assets = list_meta_assets()
    for page in assets.get("pages", []):
        if page.get("id") == page_id:
            return str(page.get("name") or page_id)
    return ""


def find_client(data: dict[str, Any], client_id: str) -> dict[str, Any]:
    for client in data.get("clients", []):
        if client.get("id") == client_id:
            return client
    raise ValueError(f"Unknown client: {client_id}")


def get_platform(client: dict[str, Any], name: str) -> dict[str, Any]:
    platforms = client.setdefault("platforms", {})
    platform = platforms.setdefault(name, {})
    return platform


def selected_account_ids(client: dict[str, Any]) -> set[str]:
    meta = client.get("platforms", {}).get("meta", {})
    ids = set()
    for account in meta.get("accounts", []):
        account_id = account.get("ad_account_id") or ""
        if not account_id:
            ids.add(account.get("ad_account_id_env", ""))
        else:
            ids.add(account_id)
    return ids


def list_meta_assets(client_id: str = "") -> dict[str, Any]:
    load_env()
    token = ""
    
    if client_id:
        try:
            data = read_json(CONFIG_PATH)
            client = find_client(data, client_id)
            token = client.get("platforms", {}).get("meta", {}).get("access_token", "")
            if not token:
                token = client.get("platforms", {}).get("organic", {}).get("access_token", "")
        except ValueError:
            pass
            
    if not token:
        token = os.environ.get("META_ADS_ACCESS_TOKEN", "").strip()
        
    api_version = os.environ.get("META_API_VERSION", "v25.0").strip() or "v25.0"
    if not token:
        return {"ad_accounts": [], "pages": [], "warnings": ["Missing META_ADS_ACCESS_TOKEN or client token."]}

    graph = GraphClient(access_token=token, api_version=api_version)
    warnings = []
    ad_accounts: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []

    async def fetch_ad_accounts() -> list[dict[str, Any]]:
        try:
            return await graph.get_paginated(
                "/me/adaccounts",
                {"fields": "id,name,account_status,currency,timezone_name", "limit": 100},
                max_rows=300,
            )
        except Exception as error:
            # Don't warn for Page tokens which naturally can't access ad accounts
            if "nonexisting field" not in str(error).lower():
                warnings.append(f"Could not list ad accounts: {error}")
            return []
            
    async def fetch_pages() -> list[dict[str, Any]]:
        try:
            return await graph.get_paginated(
                "/me/accounts",
                {
                    "fields": "id,name,instagram_business_account{id,username,name}",
                    "limit": 100,
                },
                max_rows=300,
            )
        except Exception:
            # Page Access Token: /me/accounts doesn't work, but /me IS the page
            try:
                me = await graph.get("/me", {"fields": "id,name,instagram_business_account{id,username,name}"})
                if me.get("id"):
                    return [me]
            except Exception as error:
                warnings.append(f"Could not list pages: {error}")
            return []

    async def fetch_all():
        return await asyncio.gather(fetch_ad_accounts(), fetch_pages())

    raw_accounts, raw_pages = asyncio.run(fetch_all())

    if raw_accounts:
        ad_accounts = [
            {
                "id": row.get("id", ""),
                "name": row.get("name") or row.get("id", ""),
                "status": row.get("account_status", ""),
                "currency": row.get("currency", ""),
                "timezone": row.get("timezone_name", ""),
            }
            for row in raw_accounts
        ]

    if raw_pages:
        pages = [
            {
                "id": row.get("id", ""),
                "name": row.get("name") or row.get("id", ""),
                "instagram": row.get("instagram_business_account") or None,
            }
            for row in raw_pages
        ]

    return {"ad_accounts": ad_accounts, "pages": pages, "warnings": warnings}


def app_state() -> dict[str, Any]:
    data = read_json(CONFIG_PATH)
    resolved_config = load_config(str(CONFIG_PATH), str(ENV_PATH))
    resolved_by_id = {client.id: client for client in resolved_config.clients}
    clients = []
    for client in data.get("clients", []):
        platforms = client.get("platforms", {})
        meta = platforms.get("meta", {})
        organic = platforms.get("organic", {})
        resolved_client = resolved_by_id.get(client.get("id"))
        resolved_accounts = []
        if resolved_client:
            resolved_accounts = [
                {
                    "id": account.id,
                    "name": account.name,
                    "ad_account_id": account.ad_account_id,
                    "ad_account_id_env": account.ad_account_id_env,
                }
                for account in resolved_client.meta.accounts
            ]
        clients.append(
            {
                "id": client.get("id"),
                "name": client.get("name"),
                "output_folder": client.get("output_folder", client.get("id")),
                "timezone": client.get("timezone"),
                "currency": client.get("currency"),
                "ai_token": client.get("ai_token", ""),
                "meta": {
                    "enabled": meta.get("enabled", False),
                    "access_token": meta.get("access_token", ""),
                    "accounts": resolved_accounts or meta.get("accounts", []),
                    "fields": meta.get("fields", DEFAULT_META_FIELDS),
                    "levels": meta.get("levels", ["campaign"]),
                },
                "organic": {
                    "enabled": organic.get("enabled", False),
                    "access_token": organic.get("access_token", ""),
                    "page_id": organic.get("page_id", ""),
                    "page_id_env": organic.get("page_id_env", "META_PAGE_ID"),
                    "instagram_account_id": organic.get("instagram_account_id", ""),
                    "instagram_account_id_env": organic.get(
                        "instagram_account_id_env", "META_INSTAGRAM_ACCOUNT_ID"
                    ),
                    "facebook_enabled": organic.get("facebook_enabled", True),
                    "instagram_enabled": organic.get("instagram_enabled", True),
                    "facebook_post_insight_metrics": organic.get(
                        "facebook_post_insight_metrics", DEFAULT_FACEBOOK_POST_INSIGHT_METRICS
                    ),
                    "instagram_media_insight_metrics": organic.get(
                        "instagram_media_insight_metrics", DEFAULT_INSTAGRAM_MEDIA_INSIGHT_METRICS
                    ),
                },
            }
        )

    return {
        "clients": clients,
        "metric_options": {
            "paid": PAID_METRIC_OPTIONS,
            "facebook_organic": FACEBOOK_ORGANIC_METRIC_OPTIONS,
            "instagram_organic": INSTAGRAM_ORGANIC_METRIC_OPTIONS,
            "required_paid": REQUIRED_META_FIELDS,
        },
    }


def save_dashboard_config(payload: dict[str, Any]) -> dict[str, Any]:
    data = read_json(CONFIG_PATH)
    client_id = payload.get("client_id")
    client = find_client(data, client_id)
    client["name"] = payload.get("client_name") or client.get("name") or client_id
    client["timezone"] = payload.get("timezone") or client.get("timezone") or "Africa/Cairo"
    client["currency"] = payload.get("currency") or client.get("currency") or "EGP"
    page_name = str(payload.get("page_name") or "").strip()
    if not page_name:
        page_name = page_name_from_assets(str(payload.get("page_id") or ""))
    selected_accounts = payload.get("ad_accounts") or []
    primary_account_name = ""
    if selected_accounts:
        primary_account_name = str(selected_accounts[0].get("name") or selected_accounts[0].get("id") or "")
    client["output_folder"] = safe_folder_name(
        page_name or primary_account_name or client.get("name") or client_id,
        client_id,
    )
    
    if payload.get("ai_token") is not None:
        client["ai_token"] = payload.get("ai_token", "").strip()

    meta = get_platform(client, "meta")
    
    if payload.get("ads_token"):
        meta["access_token"] = payload["ads_token"]
        
    meta.setdefault("access_token_env", "META_ADS_ACCESS_TOKEN")
    meta.setdefault("api_version_env", "META_API_VERSION")
    meta["levels"] = ["campaign"]

    meta["enabled"] = bool(selected_accounts)
    meta["accounts"] = [
        {
            "id": slug(account.get("name") or account.get("id") or f"account_{index}"),
            "name": account.get("name") or account.get("id") or f"Ad Account {index}",
            "ad_account_id": account.get("id"),
        }
        for index, account in enumerate(selected_accounts, start=1)
        if account.get("id")
    ]
    chosen_paid = [item for item in payload.get("paid_metrics", []) if isinstance(item, str)]
    meta["fields"] = unique(REQUIRED_META_FIELDS + chosen_paid)

    organic = get_platform(client, "organic")
    
    if payload.get("organic_token"):
        organic["access_token"] = payload["organic_token"]
        
    organic.setdefault("page_id_env", "META_PAGE_ID")
    organic.setdefault("access_token_env", "META_ORGANIC_ACCESS_TOKEN")
    organic.setdefault(
        "fallback_access_token_envs",
        ["META_PAGE_ACCESS_TOKEN", "META_ACCESS_TOKEN", "META_ADS_ACCESS_TOKEN"],
    )
    organic.setdefault("instagram_account_id_env", "META_INSTAGRAM_ACCOUNT_ID")
    organic.setdefault("instagram_access_token_env", "META_IG_ACCESS_TOKEN")
    organic.setdefault(
        "instagram_fallback_access_token_envs",
        ["META_ADS_ACCESS_TOKEN", "META_ORGANIC_ACCESS_TOKEN", "META_ACCESS_TOKEN"],
    )
    organic["facebook_enabled"] = bool(payload.get("facebook_enabled", True))
    organic["instagram_enabled"] = bool(payload.get("instagram_enabled", True))
    organic["page_id"] = payload.get("page_id", "")
    organic["instagram_account_id"] = payload.get("instagram_account_id", "")
    
    organic["enabled"] = bool(organic["page_id"] or organic["instagram_account_id"])

    organic["max_facebook_posts"] = int(payload.get("max_facebook_posts") or 100)
    organic["max_instagram_media"] = int(payload.get("max_instagram_media") or 100)
    organic["facebook_post_insight_metrics"] = [
        item for item in payload.get("facebook_organic_metrics", []) if isinstance(item, str)
    ]
    organic["instagram_media_insight_metrics"] = [
        item for item in payload.get("instagram_organic_metrics", []) if isinstance(item, str)
    ]

    if not meta["enabled"] and not organic["enabled"]:
        raise ValueError("You must choose at least one Ad Account OR one Facebook/Instagram Page.")

    write_json(CONFIG_PATH, data)
    return {"ok": True, "config": app_state()}


def run_report(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = payload.get("client_id") or "client_demo"
    month = payload.get("month") or ""
    since_date = payload.get("since") or ""
    until_date = payload.get("until") or ""
    
    command = [
        sys.executable,
        "-m",
        "social_reports.cli",
        "--client",
        client_id,
    ]
    if since_date and until_date:
        command.extend(["--since", since_date, "--until", until_date])
    elif month:
        command.extend(["--month", month])

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    
    data = read_json(CONFIG_PATH)
    try:
        client = find_client(data, client_id)
        if client.get("ai_token"):
            env["OPENROUTER_API_KEY"] = client.get("ai_token")
    except ValueError:
        pass
        
    # Reset status file before starting
    status_path = output_root_for_client(client_id, month or f"{since_date}_to_{until_date}") / "pipeline_status.json"
    if status_path.exists():
        status_path.unlink()
        
    process = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=360,
    )
    output = (process.stdout + process.stderr).strip()
    report_path = None
    for line in output.splitlines():
        if "Report generated:" in line:
            report_path = line.split("Report generated:", 1)[1].strip()
            break
    return {
        "ok": process.returncode == 0,
        "exit_code": process.returncode,
        "output": output,
        "report_path": str((ROOT / report_path).resolve()) if report_path else "",
    }


def read_report(query: dict[str, list[str]]) -> dict[str, Any]:
    client_id = query.get("client", ["client_demo"])[0]
    period = query.get("period", [""])[0]
    kind = query.get("kind", ["standard"])[0]
    if not period:
        raise ValueError("period is required")
    filename = "ai_monthly_report.md" if kind == "ai" else "monthly_social_report.md"
    path = output_root_for_client(client_id, period) / filename
    if not path.exists():
        return {"ok": False, "content": "", "path": str(path), "message": "Report not found."}
    return {"ok": True, "content": path.read_text(encoding="utf-8"), "path": str(path)}


def read_details(query: dict[str, list[str]]) -> dict[str, Any]:
    client_id = query.get("client", ["client_demo"])[0]
    period = query.get("period", [""])[0]
    if not period:
        raise ValueError("period is required")

    root = output_root_for_client(client_id, period)
    processed = root / "processed"
    organic_content = read_csv(processed / "organic_content.csv")
    kpis_path = processed / "monthly_kpis.json"
    organic_summary_path = processed / "organic_summary.json"
    ai_status_path = processed / "ai_report_status.json"
    organic_diagnostics_path = root / "raw" / "organic_diagnostics.json"

    kpis = read_json(kpis_path) if kpis_path.exists() else {}
    organic_summary = read_json(organic_summary_path) if organic_summary_path.exists() else {}
    ai_status = read_json(ai_status_path) if ai_status_path.exists() else {}
    organic_diagnostics = read_json(organic_diagnostics_path) if organic_diagnostics_path.exists() else {}
    warnings = organic_diagnostics.get("warnings", [])
    
    campaigns = kpis.get("campaigns", [])

    organic_content = sorted(
        organic_content,
        key=lambda row: (
            float(row.get("engagements") or 0),
            float(row.get("views") or 0),
        ),
        reverse=True,
    )
    campaigns = sorted(
        campaigns,
        key=lambda row: float(row.get("spend") or 0),
        reverse=True,
    )

    return {
        "ok": root.exists(),
        "root": str(root),
        "organic_summary": organic_summary,
        "organic_content": organic_content[:200],
        "campaigns": campaigns[:200],
        "stories": {
            "available": False,
            "message": (
                "Stories are not collected in this run. Instagram stories need a linked IG "
                "Business/Creator account and a separate stories polling step because story "
                "media is short-lived."
            ),
        },
        "ai_report": ai_status,
        "warnings": warnings,
    }


def validate_tokens(payload: dict[str, Any]) -> dict[str, Any]:
    ads_token = payload.get("ads_token", "").strip()
    organic_token = payload.get("organic_token", "").strip()
    
    async def check_token(token: str) -> dict[str, Any]:
        if not token:
            return {"valid": False, "message": "No token provided"}
        graph = GraphClient(access_token=token)
        try:
            me = await graph.get("/me", {"fields": "id,name"})
            token_name = me.get("name", "Unknown")
            
            # Try to get permissions (works for User tokens only)
            perm_list = []
            try:
                permissions = await graph.get_paginated("/me/permissions")
                perm_list = [p["permission"] for p in permissions if p.get("status") == "granted"]
            except Exception:
                # Page Access Tokens don't support /me/permissions — that's OK
                perm_list = ["page_token"]
            
            return {
                "valid": True,
                "name": token_name,
                "permissions": perm_list
            }
        except Exception as error:
            return {"valid": False, "message": str(error)}

    async def run_checks():
        return await asyncio.gather(
            check_token(ads_token),
            check_token(organic_token)
        )
        
    ads_result, organic_result = asyncio.run(run_checks())
    return {
        "ads": ads_result,
        "organic": organic_result
    }

def read_status(query: dict[str, list[str]]) -> dict[str, Any]:
    client_id = query.get("client_id", [""])[0]
    period = query.get("period", [""])[0]
    
    if not client_id or not period:
        return {"ok": False, "step": 0, "message": "Missing parameters"}
        
    status_path = output_root_for_client(client_id, period) / "pipeline_status.json"
    if status_path.exists():
        try:
            return read_json(status_path)
        except Exception:
            pass
            
    return {"ok": True, "step": 0, "message": "Initializing pipeline..."}


def export_pptx(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate a branded PPTX on demand from report data."""
    from social_reports.presentation import generate_pptx_from_data
    client_id = payload.get("client_id", "client_demo")
    period = payload.get("period", "")
    if not period:
        raise ValueError("period is required")

    root = output_root_for_client(client_id, period)
    data = read_json(CONFIG_PATH)
    client = find_client(data, client_id)
    kpis_path = root / "processed" / "monthly_kpis.json"
    organic_path = root / "processed" / "organic_summary.json"
    kpis = read_json(kpis_path) if kpis_path.exists() else {}
    organic = read_json(organic_path) if organic_path.exists() else None

    pptx_path = root / f"{client_id}_report.pptx"
    ok = generate_pptx_from_data(
        pptx_path,
        client_name=client.get("name", client_id),
        period=period,
        currency=client.get("currency", "EGP"),
        current_kpis=kpis.get("current", {}),
        previous_kpis=kpis.get("previous", {}),
        changes=kpis.get("changes", {}),
        campaigns=kpis.get("campaigns", []),
        organic_summary=organic,
    )
    return {"ok": ok, "path": str(pptx_path)}


def export_pdf(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate a branded PDF from the (possibly edited) AI report."""
    from social_reports.pdf_export import generate_pdf_from_markdown
    client_id = payload.get("client_id", "client_demo")
    period = payload.get("period", "")
    report_content = payload.get("report_content", "").strip()
    if not period:
        raise ValueError("period is required")

    root = output_root_for_client(client_id, period)
    data = read_json(CONFIG_PATH)
    client = find_client(data, client_id)

    # Use provided (edited) content or fall back to saved file
    if not report_content:
        ai_path = root / "ai_monthly_report.md"
        std_path = root / "monthly_social_report.md"
        for path in (ai_path, std_path):
            if path.exists():
                report_content = path.read_text(encoding="utf-8")
                break

    if not report_content:
        raise ValueError("No report content available")

    pdf_path = root / f"{client_id}_report.pdf"
    ok = generate_pdf_from_markdown(
        report_content, pdf_path,
        client_name=client.get("name", client_id),
        period=period,
    )
    return {"ok": ok, "path": str(pdf_path)}

class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "SocialReportsDashboard/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self.serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            elif parsed.path == "/styles.css":
                self.serve_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
            elif parsed.path == "/app.js":
                self.serve_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
            elif parsed.path == "/api/config":
                self.send_json(app_state())
            elif parsed.path == "/api/meta/assets":
                query = parse_qs(parsed.query)
                client_id = query.get("client", [""])[0]
                self.send_json(list_meta_assets(client_id))
            elif parsed.path == "/api/report":
                self.send_json(read_report(parse_qs(parsed.query)))
            elif parsed.path == "/api/details":
                self.send_json(read_details(parse_qs(parsed.query)))
            elif parsed.path == "/api/status":
                self.send_json(read_status(parse_qs(parsed.query)))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as error:  # pragma: no cover - diagnostics for local app
            self.send_json({"ok": False, "error": str(error), "trace": traceback.format_exc()}, 500)

    def do_POST(self) -> None:
        try:
            payload = self.read_payload()
            parsed = urlparse(self.path)
            if parsed.path == "/api/config":
                self.send_json(save_dashboard_config(payload))
            elif parsed.path == "/api/run":
                self.send_json(run_report(payload))
            elif parsed.path == "/api/tokens/validate":
                self.send_json(validate_tokens(payload))
            elif parsed.path == "/api/export/pptx":
                result = export_pptx(payload)
                if result["ok"]:
                    self.send_file(Path(result["path"]), "application/vnd.openxmlformats-officedocument.presentationml.presentation")
                else:
                    self.send_json(result, 500)
            elif parsed.path == "/api/export/pdf":
                result = export_pdf(payload)
                if result["ok"]:
                    self.send_file(Path(result["path"]), "application/pdf")
                else:
                    self.send_json(result, 500)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as error:  # pragma: no cover - diagnostics for local app
            self.send_json({"ok": False, "error": str(error), "trace": traceback.format_exc()}, 500)

    def read_payload(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path, content_type: str) -> None:
        """Send a binary file as download."""
        if not path.exists():
            self.send_json({"ok": False, "error": "File not found"}, 404)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local social reports dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard running on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
