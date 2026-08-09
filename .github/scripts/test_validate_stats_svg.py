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
            r'<style>.x{fill:u\72l(https://evil.example/x)}</style>',
            r'<style>@\69mport "https://evil.example/x.css";</style>',
            '<style>.x{fill:u/**/rl(https://evil.example/x)}</style>',
            '<style>@import "https://evil.example/x.css";</style>',
            '<text style="fill:u&#x72;l(https://evil.example/x)">styled</text>',
            '<text fill="url(https://evil.example/x)">external fill</text>',
            r'<text filter="u\72l(https://evil.example/x)">escaped filter</text>',
            '<text style="background-image:image-set(&quot;https://evil.example/x.png&quot; 1x)">image set</text>',
            '<text style="background-image:image-set(&quot;relative.png&quot; 1x)">relative image set</text>',
            '<text style="background-image:-webkit-image-set(&quot;relative.png&quot; 1x)">vendor image set</text>',
            r'<text style="background-image:image-\73 et(&quot;relative.png&quot; 1x)">escaped image set</text>',
            '<text style="background-image:image/**/-set(&quot;relative.png&quot; 1x)">comment image set</text>',
            '<text style="background-image:ImAgE-SeT (&quot;relative.png&quot; 1x)">mixed image set</text>',
            '<text style="background-image:cross-fade(red, blue, 50%)">cross fade</text>',
            '<text style="background-image:element(#relative)">element image</text>',
            '<text style="background-image:image(&quot;relative.png&quot;)">image function</text>',
            '<style>.x{background-image:image-set("//evil.example/x.png" 1x)}</style>',
            '<style>.x{content:"data:text/html,evil"}</style>',
            '<style>.x{content:"file:/etc/passwd"}</style>',
            '<style>@font-face{src:src("relative.woff2")}</style>',
            '<style>@font-face{src:src("https://evil.example/font.woff2")}</style>',
            '<style>@font-face{src:src("data:font/woff2,evil")}</style>',
            r'<style>@font-face{src:s\72 c("relative.woff2")}</style>',
            '<style>@font-face{src:s/**/rc("relative.woff2")}</style>',
            '<style>@font-face{src:SrC ( "relative.woff2" )}</style>',
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
        safe = (
            '<use href="#safe-shape"/>'
            '<style>.x { fill: UrL ( "#safe-shape" ); stroke: url(#other); filter: url( ) }</style>'
            '<style>@font-face { src: SRC("#safe-font"); } .empty { src: src( ); }</style>'
            '<text style="fill: URL(\'#safe-shape\')" fill="#3178c6" stroke="currentColor" '
            'filter="url(#safe-filter)" clip-path="url(#safe-clip)">safe</text>'
        )
        self.validate_text("stats.svg", card("GitHub Stats", safe))

    def test_accepts_realistic_generated_stats_card(self) -> None:
        realistic = (
            '<svg width="495" height="195" viewBox="0 0 495 195" version="1.1" '
            'xmlns="http://www.w3.org/2000/svg" role="img" '
            'aria-labelledby="descId">'
            '<title id="titleId">Ketose333\'s GitHub Stats, Rank: A+</title>'
            '<desc id="descId">Total Stars Earned: 12, Total Commits in 2026: 340, '
            'Total PRs: 21, Total Issues: 8, Contributed to: 3</desc>'
            '<style>'
            '.header { font: 600 18px sans-serif; fill: #2f80ed; }'
            '.stat { font: 600 14px sans-serif; fill: #434d58; }'
            '.stagger { opacity: 0; }'
            '.rank-text { font: 800 24px sans-serif; fill: #434d58; }'
            '.bold { font-weight: 700; }'
            '.icon { fill: #4c71f2; display: block; }'
            '</style>'
            '<rect x="0.5" y="0.5" rx="4.5" height="99%" stroke="#e4e2e2" '
            'width="494" fill="#fffefe" stroke-opacity="1"/>'
            '<g transform="translate(25, 35)">'
            '<text x="0" y="0" class="header">Ketose333\'s GitHub Stats</text>'
            '</g>'
            '<g transform="translate(0, 55)">'
            '<svg x="25">'
            '<g class="stagger" transform="translate(25, 0)">'
            '<svg class="icon" x="0" y="-9" viewBox="0 0 16 16" '
            'width="16" height="16">'
            '<path d="M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 '
            '01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l'
            '-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 '
            '01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25z"/>'
            '</svg>'
            '<text class="stat bold" x="25" y="12.5">Total Stars Earned:</text>'
            '<text class="stat bold" x="219.01" y="12.5">12</text>'
            '</g>'
            '<g class="stagger" transform="translate(25, 25)">'
            '<text class="stat bold" x="25" y="12.5">Total Commits:</text>'
            '<text class="stat bold" x="219.01" y="12.5">340</text>'
            '</g>'
            '</svg>'
            '</g>'
            '<g transform="translate(400, 100)">'
            '<circle class="rank-circle-rim" cx="-10" cy="8" r="40" '
            'fill="none" stroke="#2f80ed"/>'
            '<text x="-10" y="14" class="rank-text">A+</text>'
            '</g>'
            '</svg>'
        )
        self.assertNotIn("error", realistic.lower())
        self.validate_text("stats.svg", realistic)

    def test_accepts_harmless_error_substring(self) -> None:
        harmless = card(
            "Ketose333's GitHub Stats",
            '<style>.error-free-badge { fill: #2f80ed; }</style>'
            '<desc>Build status: 0 errors, 0 warnings</desc>'
            '<text class="error-free-badge">Terror Bay repository</text>',
        )
        self.validate_text("stats.svg", harmless)

    def test_bootstrap_is_safe_but_not_a_generated_card(self) -> None:
        bootstrap = Path(__file__).parents[2] / "profile" / "stats.svg"
        VALIDATOR.validate(bootstrap, allow_placeholder=True)
        with self.assertRaises(ValueError):
            VALIDATOR.validate(bootstrap)


if __name__ == "__main__":
    unittest.main()
