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


def app_spotlight(app: dict[str, Any]) -> str:
    name = str(app.get("trackName") or "Invoice Monitoring").strip()
    app_url = str(app.get("trackViewUrl") or APP_STORE_FALLBACK_URL).strip()
    minimum_os = str(app.get("minimumOsVersion") or "N/A").strip()
    version = str(app.get("version") or "N/A").strip()

    name_html = html.escape(name, quote=True)
    app_url_html = html.escape(app_url, quote=True)

    return (
        f"🧾 [**{name_html}**]({app_url_html}) - "
        "On-device invoice scanning and price tracking "
        f"`iOS {minimum_os}+` `v{version}`<br/>"
    )


def replace_block(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.compile(
        rf"({re.escape(start)})(.*?)({re.escape(end)})",
        flags=re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f"Missing README markers: {start} … {end}")
    return text[: match.start(2)] + replacement.rstrip() + text[match.end(2) :]


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
