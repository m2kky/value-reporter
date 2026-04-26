from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from social_reports.config import load_dotenv
from social_reports.graph_client import GraphApiError, GraphClient


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(Path(".env"))
    token = os.environ.get("META_ADS_ACCESS_TOKEN", "").strip()
    api_version = os.environ.get("META_API_VERSION", "v25.0").strip() or "v25.0"
    if not token:
        print("Missing META_ADS_ACCESS_TOKEN in .env")
        return 1

    graph = GraphClient(access_token=token, api_version=api_version)
    try:
        pages = graph.get_paginated(
            "/me/accounts",
            {
                "fields": "id,name,instagram_business_account{id,username,name}",
                "limit": 50,
            },
            max_rows=200,
        )
    except GraphApiError as error:
        print(f"Could not list pages: {error}")
        return 1

    print(json.dumps(pages, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
