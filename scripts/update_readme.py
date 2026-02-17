#!/usr/bin/env python3
"""Update sections in README.md with a live list of public repos.

This keeps the profile README looking "alive" without manual edits.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
import urllib.request
from typing import Any

USERNAME = os.environ.get("GITHUB_USERNAME", "theos2node")
API = "https://api.github.com"


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


def md_escape(s: str) -> str:
    return (s or "").replace("\r", " ").replace("\n", " ").strip()


def fmt_repo_line(r: dict[str, Any]) -> str:
    name = r["name"]
    url = r["html_url"]
    desc = md_escape(r.get("description") or "")
    lang = r.get("language") or ""
    stars = r.get("stargazers_count")
    fork = r.get("fork")
    pushed = (r.get("pushed_at") or "")[:10]

    tags = []
    if lang:
        tags.append(f"`{lang}`")
    if fork:
        tags.append("`fork`")
    if isinstance(stars, int) and stars > 0:
        tags.append(f"`{stars} stars`")
    if pushed:
        tags.append(f"`updated {pushed}`")

    tail = ""
    if tags:
        tail = " " + " ".join(tags)

    if desc:
        return f"- [{name}]({url}) - {desc}{tail}"
    return f"- [{name}]({url}){tail}"


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

    current = repos[:8]
    current_block = "\n".join(fmt_repo_line(r) for r in current) if current else "- (no public repos found)"

    all_block = "\n".join(fmt_repo_line(r) for r in repos) if repos else "- (no public repos found)"

    today = _dt.date.today().isoformat()

    readme2 = readme
    readme2 = replace_block(readme2, "<!-- current-projects:start -->", "<!-- current-projects:end -->", current_block)
    readme2 = replace_block(readme2, "<!-- repos:start -->", "<!-- repos:end -->", all_block)
    readme2 = replace_block(readme2, "<!-- updated:start -->", "<!-- updated:end -->", today)

    if readme2 != readme:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
