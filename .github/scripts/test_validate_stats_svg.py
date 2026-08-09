#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_stats_svg.py")
SPEC = importlib.util.spec_from_file_location("validate_stats_svg", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def card(title: str, extra: str = "") -> str:
    padding = "validated generated card content " * 4
    return f'<svg xmlns="http://www.w3.org/2000/svg"><title>{title}</title><text>{padding}</text>{extra}</svg>'


class ValidateStatsSvgTest(unittest.TestCase):
    def validate_text(self, filename: str, text: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / filename
            path.write_text(text, encoding="utf-8")
            VALIDATOR.validate(path)

    def test_accepts_expected_cards(self) -> None:
        self.validate_text("stats.svg", card("Ketose333's GitHub Stats"))
        self.validate_text("top-langs.svg", card("Most Used Languages"))

    def test_rejects_active_or_external_content(self) -> None:
        payloads = (
            '<script>alert(1)</script>',
            '<foreignObject><div>HTML</div></foreignObject>',
            '<text onload="alert(1)">event</text>',
            '<a href="https://evil.example">external</a>',
            '<a href="javascript:alert(1)">script URL</a>',
            '<a href="java&#x09;script:alert(1)">entity tab URL</a>',
            '<a href="java\nscript:alert(1)">newline URL</a>',
            '<a href="data:text/html,evil">data URL</a>',
            '<a href="relative.svg">relative URL</a>',
            '<style>.x{fill:url(https://evil.example/x)}</style>',
            '<style>.x{fill:u&#x72;l(https://evil.example/x)}</style>',
            '<style>@import "https://evil.example/x.css";</style>',
            '<text style="fill:u&#x72;l(https://evil.example/x)">styled</text>',
            '<animate attributeName="x" values="0;1"/>',
            '<set attributeName="href" to="https://evil.example"/>',
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.validate_text("stats.svg", card("GitHub Stats", payload))

    def test_rejects_doctype_error_and_placeholder(self) -> None:
        payloads = (
            '<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>' + card("GitHub Stats"),
            '<?xml-stylesheet href="https://evil.example/x.css"?>' + card("GitHub Stats"),
            card("GitHub Stats", "<text>Something went wrong: Maximum retries exceeded</text>"),
            card("GitHub Stats").replace("<svg ", '<svg data-portfolio-placeholder="true" '),
        )
        for payload in payloads:
            with self.subTest(payload=payload[:40]):
                with self.assertRaises(ValueError):
                    self.validate_text("stats.svg", payload)

    def test_rejects_wrong_identity(self) -> None:
        with self.assertRaises(ValueError):
            self.validate_text("top-langs.svg", card("Unrelated SVG"))

    def test_accepts_internal_fragment_reference(self) -> None:
        self.validate_text("stats.svg", card("GitHub Stats", '<use href="#safe-shape"/>'))

    def test_bootstrap_is_safe_but_not_a_generated_card(self) -> None:
        bootstrap = Path(__file__).parents[2] / "profile" / "stats.svg"
        VALIDATOR.validate(bootstrap, allow_placeholder=True)
        with self.assertRaises(ValueError):
            VALIDATOR.validate(bootstrap)


if __name__ == "__main__":
    unittest.main()
