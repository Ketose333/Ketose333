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
    rb"<!DOCTYPE|<!ENTITY|<\?(?!xml\s+version\s*=)|@import|javascript\s*:|"
    rb"something went wrong|maximum retries|"
    rb"deployment[ _-]*(?:paused|unavailable)|service unavailable|rate.?limit|"
    rb"(?:^|[^a-z])error(?:[^a-z]|$)",
    re.IGNORECASE,
)
PLACEHOLDER = re.compile(rb"data-portfolio-placeholder|bootstrap placeholder", re.IGNORECASE)
ACTIVE_TAGS = {"script", "foreignobject", "iframe", "object", "embed", "animate", "set"}
URL_ATTRIBUTES = {"href", "src"}
RESOURCE_ATTRIBUTES = {
    "clip-path", "color-profile", "cursor", "fill", "filter", "marker",
    "marker-end", "marker-mid", "marker-start", "mask", "stroke",
}
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
SCHEME_WHITESPACE = re.compile(r"[\s\x00-\x1f\x7f]+")
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_ESCAPE = re.compile(
    r"\\(?:([0-9a-fA-F]{1,6})(?:\r\n|[ \t\r\n\f])?|(\r\n|[\n\r\f])|(.))",
    re.DOTALL,
)
CSS_URL = re.compile(r"url\s*\(", re.IGNORECASE)
FRAGMENT = re.compile(r"#[A-Za-z_][A-Za-z0-9_.:-]*")
EXTERNAL_CSS_SCHEME = re.compile(r"(?:https?|data|javascript|file)\s*:|//", re.IGNORECASE)
EXPECTED_TEXT = {
    "stats.svg": ("github stats",),
    "top-langs.svg": ("most used languages", "top languages"),
}


def local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1].lower()


def decode_css_escape(match: re.Match[str]) -> str:
    if match.group(1):
        codepoint = int(match.group(1), 16)
        if codepoint == 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
            return "\N{REPLACEMENT CHARACTER}"
        return chr(codepoint)
    if match.group(2):
        return ""
    return match.group(3)


def canonicalize_css(value: str) -> str:
    without_comments = CSS_COMMENT.sub("", value)
    decoded = CSS_ESCAPE.sub(decode_css_escape, without_comments)
    return CONTROL.sub("", decoded)


def validate_css(value: str) -> None:
    canonical = canonicalize_css(value)
    if re.search(r"@\s*import\b", canonical, re.IGNORECASE):
        raise ValueError("CSS @import is not allowed")
    if EXTERNAL_CSS_SCHEME.search(canonical):
        raise ValueError("external CSS resource token is not allowed")
    position = 0
    while match := CSS_URL.search(canonical, position):
        closing = canonical.find(")", match.end())
        if closing < 0:
            raise ValueError("malformed CSS url()")
        target = canonical[match.end():closing].strip()
        if target[:1] in {'"', "'"}:
            quote = target[0]
            if len(target) < 2 or target[-1] != quote:
                raise ValueError("malformed quoted CSS url()")
            target = target[1:-1].strip()
        if target and not FRAGMENT.fullmatch(target):
            normalized = SCHEME_WHITESPACE.sub("", target).lower()
            raise ValueError(f"only empty or fragment CSS url() is allowed: {normalized[:24]}")
        position = closing + 1


def validate(path: Path, *, allow_placeholder: bool = False) -> None:
    expected = EXPECTED_TEXT.get(path.name)
    if expected is None:
        raise ValueError(f"unexpected card filename: {path.name}")
    raw = path.read_bytes()
    if not MIN_BYTES <= len(raw) <= MAX_BYTES:
        raise ValueError(f"card size outside {MIN_BYTES}..{MAX_BYTES} bytes: {len(raw)}")
    if FORBIDDEN_RAW.search(raw):
        raise ValueError("forbidden active/error content")
    if not allow_placeholder and PLACEHOLDER.search(raw):
        raise ValueError("placeholder content is not a generated card")
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
            if CONTROL.search(value):
                raise ValueError(f"control character is not allowed in {name}")
            if name in URL_ATTRIBUTES:
                normalized = SCHEME_WHITESPACE.sub("", value).lower()
                if value and not value.startswith("#"):
                    raise ValueError(f"only empty or fragment {name} is allowed: {normalized[:24]}")
            if name == "style" or name in RESOURCE_ATTRIBUTES:
                validate_css(value)
        if local_name(element.tag) == "style":
            validate_css("".join(element.itertext()))
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
