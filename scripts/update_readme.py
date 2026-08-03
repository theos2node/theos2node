#!/usr/bin/env python3
"""Refresh the App Store details shown in the profile README."""

from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Any

APP_STORE_APP_ID = os.environ.get("APP_STORE_APP_ID", "6753273634")
APP_STORE_COUNTRY = os.environ.get("APP_STORE_COUNTRY", "ph")
APP_STORE_FALLBACK_URL = (
    "https://apps.apple.com/ph/app/invoice-monitoring/id6753273634"
)
APP_STORE_BADGE_URL = (
    "https://tools.applemediaservices.com/api/badges/"
    "download-on-the-app-store/black/en-us?size=250x83"
)


def fetch_app_store_app(app_id: str, country: str) -> dict[str, Any]:
    app_id_q = urllib.parse.quote(app_id, safe="")
    country_q = urllib.parse.quote(country, safe="")
    url = f"https://itunes.apple.com/lookup?id={app_id_q}&country={country_q}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or not results:
        raise RuntimeError("The App Store lookup returned no matching app.")

    app = results[0]
    if not isinstance(app, dict):
        raise RuntimeError("The App Store lookup returned an unexpected result.")
    return app


def shields_value(value: str) -> str:
    return urllib.parse.quote(value.replace("-", "--"), safe="")


def shields_badge(
    label: str, message: str, color: str, logo: str | None = None
) -> str:
    url = (
        f"https://img.shields.io/badge/{shields_value(label)}-"
        f"{shields_value(message)}-{color}?style=flat"
    )
    if logo:
        url += (
            f"&logo={urllib.parse.quote(logo, safe='')}"
            "&logoColor=white"
        )
    return url


def app_spotlight(app: dict[str, Any]) -> str:
    name = str(app.get("trackName") or "Invoice Monitoring").strip()
    app_url = str(app.get("trackViewUrl") or APP_STORE_FALLBACK_URL).strip()
    icon_url = str(app.get("artworkUrl100") or app.get("artworkUrl512") or "").strip()
    minimum_os = str(app.get("minimumOsVersion") or "N/A").strip()
    version = str(app.get("version") or "N/A").strip()

    name_html = html.escape(name, quote=True)
    app_url_html = html.escape(app_url, quote=True)
    icon_url_html = html.escape(icon_url, quote=True)
    platform_badge = shields_badge("iOS", f"{minimum_os}+", "0A84FF", "apple")
    version_badge = shields_badge("Version", version, "2EA44F")

    return "\n".join(
        [
            (
                f'<a href="{app_url_html}"><img src="{icon_url_html}" width="58" '
                f'alt="{name_html} icon" align="left" /></a>'
            ),
            (
                f'<a href="{app_url_html}"><strong>{name_html}</strong></a>&nbsp;&nbsp;'
                f'<a href="{app_url_html}"><img alt="Download on the App Store" '
                f'src="{APP_STORE_BADGE_URL}" height="28" align="absmiddle" /></a><br/>'
            ),
            "<sub>On-device invoice scanning and price tracking.</sub><br/><br/>",
            (
                f'<img alt="iOS badge" src="{platform_badge}" /> '
                f'<img alt="Version badge" src="{version_badge}" />'
            ),
            '<br clear="left"/>',
        ]
    )


def replace_block(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.compile(
        rf"({re.escape(start)})(.*?)({re.escape(end)})",
        flags=re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f"Missing README markers: {start} … {end}")
    return text[: match.start(2)] + "\n" + replacement.rstrip() + "\n" + text[match.end(2) :]


def main() -> int:
    readme_path = os.environ.get("README_PATH", "README.md")
    with open(readme_path, encoding="utf-8") as readme_file:
        original = readme_file.read()

    try:
        app = fetch_app_store_app(APP_STORE_APP_ID, APP_STORE_COUNTRY)
        updated = replace_block(
            original,
            "<!-- app-spotlight:start -->",
            "<!-- app-spotlight:end -->",
            app_spotlight(app),
        )
    except Exception as error:
        print(f"warning: App Store refresh failed: {error}", file=sys.stderr)
        return 0

    if updated != original:
        with open(readme_path, "w", encoding="utf-8") as readme_file:
            readme_file.write(updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
