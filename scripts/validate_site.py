#!/usr/bin/env python3
"""Dependency-free production checks for the static site."""

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
BASE = "https://drsemen2025.github.io/UniCertGroup-Ltd_International-Team/"


class AuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.labels: set[str] = set()
        self.controls: list[tuple[str, str]] = []
        self.links: list[str] = []
        self.main_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"] or "")
        if tag == "label" and values.get("for"):
            self.labels.add(values["for"] or "")
        if tag in {"input", "select", "textarea"}:
            self.controls.append((tag, values.get("id") or ""))
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag == "main":
            self.main_count += 1


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    parser = AuditParser()
    parser.feed(index)

    if parser.main_count != 1:
        fail(f"Expected one main landmark, found {parser.main_count}", errors)
    for tag, control_id in parser.controls:
        if not control_id or control_id not in parser.labels:
            fail(f"Unlabelled {tag}: {control_id or '[missing id]'}", errors)
    if 'href="#main-content"' not in index:
        fail("Missing skip link", errors)
    if f'<link rel="canonical" href="{BASE}"' not in index:
        fail("Canonical URL is missing or incorrect", errors)
    if "formsubmit.co" in index:
        fail("Third-party form submission must not be embedded", errors)
    if "PDF_B64" in index:
        fail("Questionnaire PDF must not be embedded in JavaScript", errors)
    if 'fetch("data/regulatory-source-status.json?ts="+Date.now()' not in index:
        fail("Cache-bypassed source-status fetch is missing", errors)

    json_ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', index, re.S)
    if not json_ld:
        fail("JSON-LD is missing", errors)
    for item in json_ld:
        try:
            json.loads(item)
        except json.JSONDecodeError as exc:
            fail(f"Invalid JSON-LD: {exc}", errors)

    required = [
        "privacy.html", "terms.html", "robots.txt", "sitemap.xml",
        "assets/favicon.svg", "assets/social-card.png",
        "downloads/UnicertGroup_Certification_Compliance_Questionnaire_Rev3.pdf",
        "data/regulatory-source-status.json",
    ]
    for relative in required:
        if not (ROOT / relative).is_file():
            fail(f"Missing required asset: {relative}", errors)

    status = json.loads((ROOT / "data/regulatory-source-status.json").read_text(encoding="utf-8"))
    source_total = sum(status["summary"].values())
    if source_total != len(status["sources"]):
        fail("Source-status summary does not match source entries", errors)
    if not status.get("legal_reviewed_at") or not status.get("checked_at"):
        fail("Source-status review timestamps are incomplete", errors)

    try:
        ET.parse(ROOT / "sitemap.xml")
    except ET.ParseError as exc:
        fail(f"Invalid sitemap XML: {exc}", errors)

    if errors:
        print("SITE VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"SITE VALIDATION PASSED: {len(parser.controls)} labelled controls, {source_total} monitored official sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
