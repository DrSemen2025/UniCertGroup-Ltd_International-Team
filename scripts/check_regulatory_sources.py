#!/usr/bin/env python3
"""Publish a factual availability snapshot for selected official sources.

This is deliberately not a legal-change detector. HTTP availability can be
checked automatically; scope, applicability, and revision meaning require a
qualified reviewer.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "regulatory-source-status.json"
LEGAL_REVIEWED_AT = "2026-07-20"

SOURCES = [
    ("EU Cyber Resilience Act — legal text", "https://eur-lex.europa.eu/eli/reg/2024/2847/oj/eng"),
    ("EU Product Liability Directive — legal text", "https://eur-lex.europa.eu/eli/dir/2024/2853/oj/eng"),
    ("EU Machinery Regulation — legal text", "https://eur-lex.europa.eu/eli/reg/2023/1230/oj/eng"),
    ("EU CRA reporting guidance", "https://digital-strategy.ec.europa.eu/en/policies/cra-reporting"),
    ("EU Cyber Resilience Act policy page", "https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act"),
    ("EU CBAM official portal", "https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism_en"),
    ("EU AI Act implementation timeline", "https://ai-act-service-desk.ec.europa.eu/en/ai-act/timeline/timeline-implementation-eu-ai-act"),
    ("EU Machinery policy page", "https://single-market-economy.ec.europa.eu/sectors/mechanical-engineering/machinery_en"),
    ("Germany CBAM definitive regime", "https://www.dehst.de/EN/Topics/CBAM/CBAM-definitive-regime-2026/cbam-definitive-regime-2026_node.html"),
    ("UK product marking by sector", "https://www.gov.uk/government/publications/product-regulations-by-sector-and-current-approaches-to-product-marking-ukca-and-ce-regimes"),
    ("UK product safety framework", "https://www.gov.uk/government/consultations/product-regulation-the-uks-new-product-safety-framework/the-uks-new-product-safety-framework"),
    ("China CCC implementation rules — April 2026", "https://www.cnca.gov.cn/hlwfw/ywzl/qzxcprz/ssgz/art/2026/art_5261f654e02d45edaf0805fb268c9fc9.html"),
]


def check(url: str) -> tuple[int, str]:
    command = [
        "curl", "-L", "--retry", "2", "--connect-timeout", "15",
        "--max-time", "60", "-A", "UnicertGroup-source-monitor/1.0",
        "-sS", "-o", "/dev/null", "-w", "%{http_code}|%{url_effective}", url,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        raw = result.stdout.strip()
        code_text, _, final_url = raw.partition("|")
        return int(code_text or 0), final_url or url
    except (OSError, ValueError):
        return 0, url


def category(code: int) -> str:
    if 200 <= code < 400:
        return "available"
    if code in {401, 403, 405, 429}:
        return "manual_review"
    return "unavailable"


def main() -> None:
    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    entries = []
    counts = {"available": 0, "manual_review": 0, "unavailable": 0}
    for name, url in SOURCES:
        code, final_url = check(url)
        status = category(code)
        counts[status] += 1
        entries.append({
            "name": name,
            "url": url,
            "final_url": final_url,
            "http_status": code,
            "status": status,
            "checked_at": checked_at,
        })
        print(f"{status.upper():13} {code:3} {name}")

    payload = {
        "schema_version": 1,
        "checked_at": checked_at,
        "legal_reviewed_at": LEGAL_REVIEWED_AT,
        "method": "Automated HTTP availability check. This does not verify legal meaning, applicability, completeness, or whether a revision changes an obligation.",
        "summary": counts,
        "sources": entries,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
