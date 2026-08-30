"""oklch -> sRGB hex conversion, pure stdlib.

Reference: Björn Ottosson's oklab/oklch (ok-scale), linear-sRGB matrices from
the CSS Color 4 spec. Gamut mapping follows the CSS spec's approach in spirit:
binary-search chroma reduction (keeps lightness + hue = perceptual intent).
Alpha suffixes (oklch(L C H / A)) map to 8-digit hex #rrggbbaa.
"""
from __future__ import annotations

import math
import re

_OKLCH_RE = re.compile(
    r"oklch\(\s*"
    r"(?P<l>[\d.]+%?)"
    r"\s+(?P<c>[\d.]+)"
    r"\s+(?P<h>[\d.]+)"
    r"(?:\s*/\s*(?P<a>[\d.]+%?))?"
    r"\s*\)"
)


def _parse_num(tok: str) -> float:
    return float(tok[:-1]) / 100.0 if tok.endswith("%") else float(tok)


def _srgb_transfer(c: float) -> float:
    """Linear-light -> sRGB gamma (CSS Color 4 formula)."""
    c = min(1.0, max(0.0, c))
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def _oklch_to_linear(L: float, C: float, H: float) -> tuple[float, float, float]:
    a = C * math.cos(math.radians(H))
    b = C * math.sin(math.radians(H))
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return r, g, bb


def _in_gamut(rgb: tuple[float, float, float], eps: float = 1e-4) -> bool:
    return all(-eps <= v <= 1.0 + eps for v in rgb)


def oklch_to_hex(l: float, c: float, h: float, alpha: float | None = None) -> str:
    """Convert oklch components to #rrggbb (or #rrggbbaa with alpha)."""
    rgb = _oklch_to_linear(l, c, h)
    if not _in_gamut(rgb):
        # gamut map: reduce chroma toward the neutral axis, preserving L and H
        lo, hi = 0.0, c
        for _ in range(32):
            mid = (lo + hi) / 2.0
            if _in_gamut(_oklch_to_linear(l, mid, h)):
                lo = mid
            else:
                hi = mid
        rgb = _oklch_to_linear(l, lo, h)
    comps = tuple(round(_srgb_transfer(v) * 255) for v in rgb)
    if alpha is None:
        return "#{:02x}{:02x}{:02x}".format(*comps)
    return "#{:02x}{:02x}{:02x}{:02x}".format(*comps, round(min(1.0, alpha) * 255))


def css_color_to_hex(value: str) -> str | None:
    """Parse an oklch() CSS string (tolerating alpha) or pass through a hex.

    Returns lowercase #rrggbb / #rrggbbaa, or None if unrecognized.
    """
    value = value.strip().lower()
    if value.startswith("#"):
        return value
    m = _OKLCH_RE.search(value)
    if not m:
        return None
    L = _parse_num(m["l"])
    C = float(m["c"])
    H = float(m["h"])
    A = _parse_num(m["a"]) if m["a"] else None
    return oklch_to_hex(L, C, H, A)
