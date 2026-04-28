from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_META_FIELDS = [
    "account_id",
    "account_name",
    "campaign_id",
    "campaign_name",
    "objective",
    "spend",
    "impressions",
    "reach",
    "frequency",
    "clicks",
    "inline_link_clicks",
    "ctr",
    "cpc",
    "cpm",
    "cpp",
    "actions",
    "action_values",
    "date_start",
    "date_stop",
]

DEFAULT_FACEBOOK_POST_INSIGHT_METRICS = [
    "post_impressions_unique",      # Reach (unique users who saw the post)
    "post_media_view",              # Views (new metric, replaces post_impressions)
    "post_clicks",                  # Total clicks on the post
    "post_video_views",             # 3-second video views
    "post_video_views_organic",     # Organic 3-second video views
    "post_reactions_by_type_total", # Reaction breakdown (like, love, etc.)
    # Deprecated in v25.0+:
    # "post_impressions",           # Replaced by post_media_view
    # "post_engaged_users",         # No longer available
]

DEFAULT_INSTAGRAM_MEDIA_INSIGHT_METRICS = [
    "views",
    "reach",
    "likes",
    "comments",
    "shares",
    "saved",
    "total_interactions",
    "plays",
    "ig_reels_aggregated_all_plays_count",
]


@dataclass(frozen=True)
class MetaAccountConfig:
    id: str
    name: str
    access_token_env: str
    ad_account_id_env: str
    access_token: str = ""
    ad_account_id: str = ""


@dataclass(frozen=True)
class MetaConfig:
    enabled: bool = False
    access_token_env: str = "META_ACCESS_TOKEN"
    ad_account_id_env: str = "META_AD_ACCOUNT_ID"
    api_version_env: str = "META_API_VERSION"
    access_token: str = ""
    ad_account_id: str = ""
    api_version: str = "v25.0"
    levels: list[str] = field(default_factory=lambda: ["campaign"])
    fields: list[str] = field(default_factory=lambda: DEFAULT_META_FIELDS.copy())
    accounts: list[MetaAccountConfig] = field(default_factory=list)


@dataclass(frozen=True)
class OrganicConfig:
    enabled: bool = False
    page_id_env: str = "META_PAGE_ID"
    access_token_env: str = "META_ORGANIC_ACCESS_TOKEN"
    fallback_access_token_envs: list[str] = field(
        default_factory=lambda: ["META_PAGE_ACCESS_TOKEN", "META_ACCESS_TOKEN", "META_ADS_ACCESS_TOKEN"]
    )
    page_id: str = ""
    access_token: str = ""
    instagram_account_id_env: str = "META_INSTAGRAM_ACCOUNT_ID"
    instagram_account_id: str = ""
    instagram_access_token_env: str = "META_IG_ACCESS_TOKEN"
    instagram_fallback_access_token_envs: list[str] = field(
        default_factory=lambda: ["META_ADS_ACCESS_TOKEN", "META_ORGANIC_ACCESS_TOKEN", "META_ACCESS_TOKEN"]
    )
    instagram_access_token: str = ""
    facebook_enabled: bool = True
    instagram_enabled: bool = True
    whatsapp_business_account_id_env: str = "META_WHATSAPP_BUSINESS_ACCOUNT_ID"
    whatsapp_business_account_id: str = ""
    max_facebook_posts: int = 200
    max_instagram_media: int = 200
    facebook_post_insight_metrics: list[str] = field(
        default_factory=lambda: DEFAULT_FACEBOOK_POST_INSIGHT_METRICS.copy()
    )
    instagram_media_insight_metrics: list[str] = field(
        default_factory=lambda: DEFAULT_INSTAGRAM_MEDIA_INSIGHT_METRICS.copy()
    )


@dataclass(frozen=True)
class ClientConfig:
    id: str
    name: str
    output_folder: str = ""
    timezone: str = "Africa/Cairo"
    currency: str = "EGP"
    meta: MetaConfig = field(default_factory=MetaConfig)
    organic: OrganicConfig = field(default_factory=OrganicConfig)


@dataclass(frozen=True)
class AppConfig:
    clients: list[ClientConfig]
    output_dir: Path


class ConfigError(ValueError):
    pass


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _read_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def safe_folder_name(value: str, fallback: str = "client") -> str:
    invalid = '<>:"/\\|?*'
    cleaned = []
    for char in value.strip():
        if ord(char) < 32 or char in invalid:
            cleaned.append("_")
        else:
            cleaned.append(char)
    folder = " ".join("".join(cleaned).split()).strip(" .")
    return folder or fallback


def _meta_account_from_dict(
    data: dict[str, Any],
    *,
    default_token_env: str,
    default_access_token: str,
    index: int,
) -> MetaAccountConfig:
    token_env = data.get("access_token_env", default_token_env)
    account_env = data.get("ad_account_id_env", f"META_AD_ACCOUNT_ID_{index}")
    account_id = data.get("ad_account_id", "") or _read_env(account_env)
    access_token = data.get("access_token", "") or _read_env(token_env) or default_access_token

    return MetaAccountConfig(
        id=data.get("id", f"account_{index}"),
        name=data.get("name", data.get("id", f"Meta Account {index}")),
        access_token_env=token_env,
        ad_account_id_env=account_env,
        access_token=access_token,
        ad_account_id=account_id,
    )


def _meta_from_dict(data: dict[str, Any]) -> MetaConfig:
    token_env = data.get("access_token_env", "META_ACCESS_TOKEN")
    ad_account_env = data.get("ad_account_id_env", "META_AD_ACCOUNT_ID")
    api_version_env = data.get("api_version_env", "META_API_VERSION")
    access_token = data.get("access_token", "") or _read_env(token_env)
    ad_account_id = data.get("ad_account_id", "") or _read_env(ad_account_env)

    raw_accounts = data.get("accounts", [])
    if raw_accounts:
        accounts = [
            _meta_account_from_dict(
                raw_account,
                default_token_env=token_env,
                default_access_token=access_token,
                index=index,
            )
            for index, raw_account in enumerate(raw_accounts, start=1)
        ]
    else:
        accounts = [
            MetaAccountConfig(
                id="default",
                name="Default Meta Ad Account",
                access_token_env=token_env,
                ad_account_id_env=ad_account_env,
                access_token=access_token,
                ad_account_id=ad_account_id,
            )
        ]

    return MetaConfig(
        enabled=bool(data.get("enabled", False)),
        access_token_env=token_env,
        ad_account_id_env=ad_account_env,
        api_version_env=api_version_env,
        access_token=access_token,
        ad_account_id=ad_account_id,
        api_version=data.get("api_version", "") or _read_env(api_version_env, "v25.0"),
        levels=list(data.get("levels", ["campaign"])),
        fields=list(data.get("fields", DEFAULT_META_FIELDS)),
        accounts=accounts,
    )


def _organic_from_dict(data: dict[str, Any]) -> OrganicConfig:
    page_id_env = data.get("page_id_env", "META_PAGE_ID")
    token_env = data.get("access_token_env", "META_ORGANIC_ACCESS_TOKEN")
    fallback_envs = list(
        data.get(
            "fallback_access_token_envs",
            ["META_PAGE_ACCESS_TOKEN", "META_ACCESS_TOKEN", "META_ADS_ACCESS_TOKEN"],
        )
    )
    access_token = data.get("access_token", "") or _read_env(token_env)
    if not access_token:
        for env_name in fallback_envs:
            access_token = _read_env(env_name)
            if access_token:
                break

    ig_token_env = data.get("instagram_access_token_env", "META_IG_ACCESS_TOKEN")
    ig_fallback_envs = list(
        data.get(
            "instagram_fallback_access_token_envs",
            ["META_ADS_ACCESS_TOKEN", "META_ORGANIC_ACCESS_TOKEN", "META_ACCESS_TOKEN"],
        )
    )
    instagram_access_token = data.get("instagram_access_token", "") or _read_env(ig_token_env)
    if not instagram_access_token:
        for env_name in ig_fallback_envs:
            instagram_access_token = _read_env(env_name)
            if instagram_access_token:
                break

    instagram_account_id_env = data.get("instagram_account_id_env", "META_INSTAGRAM_ACCOUNT_ID")

    return OrganicConfig(
        enabled=bool(data.get("enabled", False)),
        page_id_env=page_id_env,
        access_token_env=token_env,
        fallback_access_token_envs=fallback_envs,
        page_id=data.get("page_id", "") or _read_env(page_id_env),
        access_token=access_token,
        instagram_account_id_env=instagram_account_id_env,
        instagram_account_id=data.get("instagram_account_id", "") or _read_env(instagram_account_id_env),
        instagram_access_token_env=ig_token_env,
        instagram_fallback_access_token_envs=ig_fallback_envs,
        instagram_access_token=instagram_access_token,
        facebook_enabled=bool(data.get("facebook_enabled", True)),
        instagram_enabled=bool(data.get("instagram_enabled", True)),
        whatsapp_business_account_id_env=data.get("whatsapp_business_account_id_env", "META_WHATSAPP_BUSINESS_ACCOUNT_ID"),
        whatsapp_business_account_id=data.get("whatsapp_business_account_id", "") or _read_env(data.get("whatsapp_business_account_id_env", "META_WHATSAPP_BUSINESS_ACCOUNT_ID")),
        max_facebook_posts=int(data.get("max_facebook_posts", 100)),
        max_instagram_media=int(data.get("max_instagram_media", 100)),
        facebook_post_insight_metrics=list(
            data.get("facebook_post_insight_metrics", DEFAULT_FACEBOOK_POST_INSIGHT_METRICS)
        ),
        instagram_media_insight_metrics=list(
            data.get("instagram_media_insight_metrics", DEFAULT_INSTAGRAM_MEDIA_INSIGHT_METRICS)
        ),
    )


def load_config(config_path: str | None = None, env_path: str = ".env") -> AppConfig:
    load_dotenv(Path(env_path))

    resolved_config = Path(config_path or _read_env("CLIENTS_CONFIG", "clients.json"))
    if not resolved_config.exists():
        raise ConfigError(f"Missing config file: {resolved_config}")

    data = json.loads(resolved_config.read_text(encoding="utf-8"))
    clients = []
    for raw_client in data.get("clients", []):
        platforms = raw_client.get("platforms", {})
        clients.append(
            ClientConfig(
                id=raw_client["id"],
                name=raw_client.get("name", raw_client["id"]),
                output_folder=safe_folder_name(
                    raw_client.get("output_folder", "") or raw_client["id"],
                    raw_client["id"],
                ),
                timezone=raw_client.get("timezone", "Africa/Cairo"),
                currency=raw_client.get("currency", "EGP"),
                meta=_meta_from_dict(platforms.get("meta", {})),
                organic=_organic_from_dict(platforms.get("organic", {})),
            )
        )

    if not clients:
        raise ConfigError("clients.json must include at least one client.")

    return AppConfig(
        clients=clients,
        output_dir=Path(_read_env("REPORT_OUTPUT_DIR", "outputs")),
    )


def get_client(config: AppConfig, client_id: str) -> ClientConfig:
    for client in config.clients:
        if client.id == client_id:
            return client
    available = ", ".join(client.id for client in config.clients)
    raise ConfigError(f"Unknown client '{client_id}'. Available clients: {available}")
