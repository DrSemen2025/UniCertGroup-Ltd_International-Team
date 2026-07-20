#!/usr/bin/env python3
"""Dependency-free static-site validation for SEO, accessibility structure and internal links."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://drsemen2025.github.io/UniCertGroup-Ltd_International-Team/"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.in_jsonld = False
        self.jsonld_parts: list[str] = []
        self.jsonld: list[str] = []
        self.meta: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.ids: list[str] = []
        self.lang = ""
        self.h1_count = 0
        self.main_count = 0
        self.skip_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k: (v or "") for k, v in attrs}
        if tag == "html": self.lang = data.get("lang", "")
        if tag == "title": self.in_title = True
        if tag == "meta": self.meta.append(data)
        if tag in {"a", "link", "script", "img"}: self.links.append({"tag": tag, **data})
        if "id" in data: self.ids.append(data["id"])
        if tag == "h1": self.h1_count += 1
        if tag == "main": self.main_count += 1
        if tag == "a" and data.get("href") == "#main" and "skip-link" in data.get("class", ""): self.skip_link = True
        if tag == "script" and data.get("type") == "application/ld+json":
            self.in_jsonld = True
            self.jsonld_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title": self.in_title = False
        if tag == "script" and self.in_jsonld:
            self.jsonld.append("".join(self.jsonld_parts).strip())
            self.in_jsonld = False

    def handle_data(self, data: str) -> None:
        if self.in_title: self.title_parts.append(data)
        if self.in_jsonld: self.jsonld_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())

    def meta_content(self, key: str, value: str) -> str:
        for item in self.meta:
            if item.get(key, "").lower() == value.lower(): return item.get("content", "")
        return ""

    def link_href(self, rel: str) -> str:
        for item in self.links:
            if item.get("tag") == "link" and rel in item.get("rel", "").split(): return item.get("href", "")
        return ""


def page_target(page: Path, raw: str) -> Path | None:
    parsed = urlsplit(raw)
    if parsed.scheme in {"http", "https", "mailto", "tel", "data"}: return None
    if parsed.scheme or raw.startswith("#") or not parsed.path: return None
    path = Path(unquote(parsed.path))
    target = (ROOT / path.relative_to("/")) if parsed.path.startswith("/") else (page.parent / path)
    target = target.resolve()
    if target.is_dir(): target = target / "index.html"
    return target


def fail(errors: list[str], page: Path, message: str) -> None:
    errors.append(f"{page.relative_to(ROOT)}: {message}")


def main() -> int:
    errors: list[str] = []
    titles: dict[str, Path] = {}
    descriptions: dict[str, Path] = {}
    pages = sorted(ROOT.rglob("*.html"))

    for page in pages:
        parser = PageParser()
        parser.feed(page.read_text(encoding="utf-8"))
        is_404 = page.name == "404.html"
        if not parser.lang: fail(errors, page, "missing html lang")
        if not parser.title: fail(errors, page, "missing title")
        elif len(parser.title) > 65: fail(errors, page, f"title is {len(parser.title)} characters")
        elif not is_404 and parser.title in titles: fail(errors, page, f"duplicate title also used by {titles[parser.title].relative_to(ROOT)}")
        else: titles[parser.title] = page
        desc = parser.meta_content("name", "description")
        if not is_404:
            if not 50 <= len(desc) <= 170: fail(errors, page, f"description length is {len(desc)}")
            elif desc in descriptions: fail(errors, page, f"duplicate description also used by {descriptions[desc].relative_to(ROOT)}")
            else: descriptions[desc] = page
            canonical = parser.link_href("canonical")
            if not canonical.startswith(BASE): fail(errors, page, "canonical does not use the live Pages base URL")
            if not parser.meta_content("property", "og:url"): fail(errors, page, "missing og:url")
            if not parser.meta_content("property", "og:image"): fail(errors, page, "missing og:image")
            if not parser.skip_link: fail(errors, page, "missing skip link")
        if parser.h1_count != 1: fail(errors, page, f"expected one h1, found {parser.h1_count}")
        if parser.main_count != 1: fail(errors, page, f"expected one main, found {parser.main_count}")
        duplicates = [item for item, count in Counter(parser.ids).items() if count > 1]
        if duplicates: fail(errors, page, f"duplicate ids: {', '.join(duplicates)}")
        for raw in parser.jsonld:
            try: json.loads(raw)
            except json.JSONDecodeError as exc: fail(errors, page, f"invalid JSON-LD: {exc}")
        for item in parser.links:
            raw = item.get("href") or item.get("src") or ""
            target = page_target(page, raw)
            if target and not target.exists(): fail(errors, page, f"missing internal target {raw}")

    sitemap = ET.parse(ROOT / "sitemap.xml")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap_urls = {node.text for node in sitemap.findall("s:url/s:loc", ns) if node.text}
    expected = set()
    for page in pages:
        if page.name == "404.html": continue
        rel = page.relative_to(ROOT).as_posix()
        if rel == "index.html": url = BASE
        elif rel.endswith("/index.html"): url = BASE + rel[:-10]
        else: url = BASE + rel
        expected.add(url)
    for url in sorted(expected - sitemap_urls): errors.append(f"sitemap: missing {url}")
    for url in sorted(sitemap_urls - expected): errors.append(f"sitemap: unexpected {url}")

    if errors:
        print("SITE VALIDATION FAILED")
        print("\n".join(f"- {item}" for item in errors))
        return 1
    print(f"SITE VALIDATION PASSED: {len(pages)} HTML pages, {len(sitemap_urls)} indexable URLs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
