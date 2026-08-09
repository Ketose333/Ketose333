#!/usr/bin/env python3
"""Reject unsafe or invalid generated GitHub profile cards."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


MAX_BYTES = 512_000
MIN_BYTES = 100
FORBIDDEN_RAW = re.compile(
    rb"<!DOCTYPE|<!ENTITY|<\?(?!xml\s+version\s*=)|@import|javascript\s*:|data-portfolio-placeholder|"
    rb"bootstrap placeholder|something went wrong|maximum retries|"
    rb"deployment[ _-]*(?:paused|unavailable)|service unavailable|rate.?limit|"
    rb"(?:^|[^a-z])error(?:[^a-z]|$)",
    re.IGNORECASE,
)
ACTIVE_TAGS = {"script", "foreignobject", "iframe", "object", "embed"}
URL_ATTRIBUTES = {"href", "src"}
EXTERNAL_URL = re.compile(r"^(?:https?:|//|data:|javascript:)", re.IGNORECASE)
EXPECTED_TEXT = {
    "stats.svg": ("github stats",),
    "top-langs.svg": ("most used languages", "top languages"),
}


def local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1].lower()


def validate(path: Path) -> None:
    expected = EXPECTED_TEXT.get(path.name)
    if expected is None:
        raise ValueError(f"unexpected card filename: {path.name}")
    raw = path.read_bytes()
    if not MIN_BYTES <= len(raw) <= MAX_BYTES:
        raise ValueError(f"card size outside {MIN_BYTES}..{MAX_BYTES} bytes: {len(raw)}")
    if FORBIDDEN_RAW.search(raw):
        raise ValueError("forbidden active/error/placeholder content")
    if re.search(rb"url\s*\(", raw, re.IGNORECASE):
        raise ValueError("CSS url() is not allowed")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"invalid XML: {exc}") from exc
    if local_name(root.tag) != "svg":
        raise ValueError("root element must be svg")
    for element in root.iter():
        if local_name(element.tag) in ACTIVE_TAGS:
            raise ValueError(f"active element is not allowed: {local_name(element.tag)}")
        for raw_name, value in element.attrib.items():
            name = local_name(raw_name)
            if name.startswith("on"):
                raise ValueError(f"event attribute is not allowed: {name}")
            if name in URL_ATTRIBUTES and EXTERNAL_URL.match(value.strip()):
                raise ValueError(f"external URL is not allowed in {name}")
    searchable = " ".join(root.itertext()).lower()
    if not any(marker in searchable for marker in expected):
        raise ValueError(f"expected card identity missing: {' or '.join(expected)}")


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: validate_stats_svg.py SVG [SVG ...]", file=sys.stderr)
        return 2
    failed = False
    for value in argv:
        path = Path(value)
        try:
            validate(path)
            print(f"validated: {path}")
        except (OSError, ValueError) as exc:
            failed = True
            print(f"invalid: {path}: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
