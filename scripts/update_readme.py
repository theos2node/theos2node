#!/usr/bin/env python3
"""Update sections in README.md with a live list of public repos.

This keeps the profile README looking "alive" without manual edits.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Any

USERNAME = os.environ.get("GITHUB_USERNAME", "theos2node")
API = "https://api.github.com"
APP_STORE_APP_ID = os.environ.get("APP_STORE_APP_ID", "6753273634")
APP_STORE_COUNTRY = os.environ.get("APP_STORE_COUNTRY", "us")
APP_STORE_BADGE_URL = (
    "https://tools.applemediaservices.com/api/badges/"
    "download-on-the-app-store/black/en-us?size=250x83"
)
PRIVATE_PROJECTS: tuple[dict[str, str], ...] = (
    {
        "name": "Invoice Monitoring (private)",
        "url": "https://apps.apple.com/us/app/invoice-monitoring/id6753273634",
        "desc": "Published iOS app for invoice and receipt price tracking.",
    },
    {
        "name": "Bar's Bookkeeper (private)",
        "url": "https://github.com/theos2node/bars-bookkeeper",
        "desc": "Private bookkeeping workflow for bar operations.",
    },
)
EXCLUDED_PUBLIC_REPOS = {"invoice-uploaderv2.2", "bars-bookkeeper", "openclaw"}


def _gh_get(url: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        headers = {k.lower(): v for k, v in resp.headers.items()}
        return data, headers


def _json_get(url: str, headers: dict[str, str] | None = None) -> tuple[Any, dict[str, str]]:
    req = urllib.request.Request(url)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        meta = {k.lower(): v for k, v in resp.headers.items()}
        return data, meta


def _next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    # Example: <...page=2>; rel="next", <...page=4>; rel="last"
    parts = [p.strip() for p in link_header.split(",")]
    for p in parts:
        if 'rel="next"' in p:
            m = re.search(r"<([^>]+)>", p)
            return m.group(1) if m else None
    return None


def fetch_public_repos(username: str) -> list[dict[str, Any]]:
    url = f"{API}/users/{username}/repos?type=public&per_page=100&sort=pushed"
    repos: list[dict[str, Any]] = []
    while url:
        page, headers = _gh_get(url)
        if isinstance(page, list):
            repos.extend(page)
        else:
            raise RuntimeError(f"Unexpected response for {url}: {type(page)}")
        url = _next_link(headers.get("link"))
    # Only actual public repos; exclude the profile repo itself.
    out = []
    for r in repos:
        if r.get("name") == username:
            continue
        if r.get("visibility") not in (None, "public") and not r.get("private"):
            # Defensive: keep only public.
            continue
        if r.get("archived") or r.get("disabled"):
            continue
        out.append(r)
    # Ensure newest pushed first (API sort should already do this).
    out.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
    return out


def fetch_app_store_app(app_id: str, country: str = "us") -> dict[str, Any]:
    app_id_q = urllib.parse.quote(app_id, safe="")
    country_q = urllib.parse.quote(country, safe="")
    url = f"https://itunes.apple.com/lookup?id={app_id_q}&country={country_q}"
    payload, _ = _json_get(url, headers={"Accept": "application/json"})
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected App Store lookup payload.")
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise RuntimeError("No App Store results returned for configured app id.")
    app = results[0]
    if not isinstance(app, dict):
        raise RuntimeError("Unexpected App Store result object.")
    return app


def md_escape(s: str) -> str:
    return (s or "").replace("\r", " ").replace("\n", " ").strip()


def short_desc(name: str, desc: str) -> str:
    n = (name or "").lower()
    d = md_escape(desc)
    overrides = {
        "full-whisper-dictation-for-mac": "Whisper-based macOS dictation replacement.",
        "homebridge-llm-control": "Chat + LLM ops for Homebridge.",
        "rssicartographer": "Live macOS Wi-Fi RSSI/radar mapping tool.",
    }
    if n in overrides:
        return overrides[n]
    if not d:
        return ""
    # Keep just the gist: cut at separators that usually introduce feature lists.
    for sep in [":", ";", " | ", " - "]:
        i = d.find(sep)
        if i != -1 and i >= 18:
            d = d[:i]
            break
    d = d.strip()
    # Hard cap
    if len(d) > 90:
        d = d[:87].rstrip() + "..."
    if d and d[-1] not in ".!?":
        d += "."
    return d
def fmt_repo_line(r: dict[str, Any]) -> str:
    name = r["name"]
    url = r["html_url"]
    raw_desc = r.get("description") or ""
    desc = short_desc(name, raw_desc)

    if desc:
        return f"- [**{name}**]({url}) - {desc}"
    return f"- [**{name}**]({url})"


def fmt_private_project_line(project: dict[str, str]) -> str:
    name = project["name"]
    desc = project.get("desc", "").strip()
    url = project.get("url", "").strip()
    if url:
        title = f"[**{name}**]({url})"
    else:
        title = f"**{name}**"
    if desc:
        return f"- {title} - {desc}"
    return f"- {title}"


def shields_value(value: str) -> str:
    return urllib.parse.quote((value or "").replace("-", "--"), safe="")


def shields_badge(label: str, message: str, color: str, logo: str | None = None) -> str:
    base = (
        f"https://img.shields.io/badge/{shields_value(label)}-"
        f"{shields_value(message)}-{color.lstrip('#')}?style=flat"
    )
    if logo:
        logo_q = urllib.parse.quote(logo, safe="")
        return f"{base}&logo={logo_q}&logoColor=white"
    return base


def short_sentence(text: str, max_len: int = 140) -> str:
    cleaned = md_escape(text)
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)
    sentence = parts[0].strip()
    if len(sentence) <= max_len:
        return sentence
    return sentence[: max_len - 3].rstrip() + "..."


def fmt_app_spotlight_block(app: dict[str, Any]) -> str:
    name = md_escape(str(app.get("trackName") or "Invoice Monitoring"))
    app_url = md_escape(str(app.get("trackViewUrl") or PRIVATE_PROJECTS[0]["url"]))
    icon_url = md_escape(str(app.get("artworkUrl100") or app.get("artworkUrl512") or ""))
    min_os = md_escape(str(app.get("minimumOsVersion") or "N/A"))
    version = md_escape(str(app.get("version") or "N/A"))
    desc = "Scan and parse invoices and receipts to track price changes over time."

    rating_count = int(app.get("userRatingCount") or 0)
    avg_rating = app.get("averageUserRating")
    if rating_count > 0 and isinstance(avg_rating, (int, float)):
        rating_text = f"{avg_rating:.1f} stars ({rating_count})"
    else:
        rating_text = "New release"

    title_html = html.escape(name, quote=True)
    desc_html = html.escape(desc, quote=True)
    app_url_html = html.escape(app_url, quote=True)
    icon_url_html = html.escape(icon_url, quote=True)

    platform_badge = shields_badge("iOS", f"{min_os}+", "0A84FF", logo="apple")
    version_badge = shields_badge("Version", version, "2EA44F")
    rating_badge = shields_badge("Rating", rating_text, "F59E0B")

    return "\n".join(
        [
            (
                f'<a href="{app_url_html}"><img src="{icon_url_html}" width="58" '
                f'alt="{title_html} icon" align="left" /></a>'
            ),
            (
                f'<a href="{app_url_html}"><strong>{title_html}</strong></a>&nbsp;&nbsp;'
                f'<a href="{app_url_html}"><img alt="Download on the App Store" '
                f'src="{APP_STORE_BADGE_URL}" height="28" align="absmiddle" /></a><br/>'
            ),
            f"<sub>{desc_html}</sub><br/><br/>",
            (
                f'<img alt="iOS badge" src="{platform_badge}" /> '
                f'<img alt="Version badge" src="{version_badge}" /> '
                f'<img alt="Rating badge" src="{rating_badge}" />'
            ),
            '<br clear="left"/>',
        ]
    )


def replace_block(text: str, start: str, end: str, block: str) -> str:
    pat = re.compile(
        rf"({re.escape(start)})(.*)({re.escape(end)})",
        flags=re.DOTALL,
    )
    m = pat.search(text)
    if not m:
        raise RuntimeError(f"Missing markers: {start} ... {end}")
    return text[: m.start(2)] + "\n" + block.rstrip() + "\n" + text[m.end(2) :]


def main() -> int:
    readme_path = os.environ.get("README_PATH", "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    repos = fetch_public_repos(USERNAME)
    visible_repos = [
        r for r in repos if (r.get("name") or "").lower() not in EXCLUDED_PUBLIC_REPOS
    ]

    # Show private work first, then public projects (sorted by most recently pushed).
    project_lines = [fmt_private_project_line(p) for p in PRIVATE_PROJECTS]
    project_lines.extend(fmt_repo_line(r) for r in visible_repos)
    current_block = "\n".join(project_lines) if project_lines else "- (no public repos found)"

    readme2 = readme
    readme2 = replace_block(
        readme2,
        "<!-- current-projects:start -->",
        "<!-- current-projects:end -->",
        current_block,
    )

    if "<!-- app-spotlight:start -->" in readme2 and "<!-- app-spotlight:end -->" in readme2:
        try:
            app = fetch_app_store_app(APP_STORE_APP_ID, APP_STORE_COUNTRY)
            app_block = fmt_app_spotlight_block(app)
            readme2 = replace_block(
                readme2,
                "<!-- app-spotlight:start -->",
                "<!-- app-spotlight:end -->",
                app_block,
            )
        except Exception as exc:
            print(f"warning: app spotlight refresh failed: {exc}", file=sys.stderr)

    if readme2 != readme:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
