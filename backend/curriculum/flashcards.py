"""Visual flashcards - SVG for the on-screen preview, fpdf2 for print/PDF.

Illustrations use locally available glyphs (emoji) and simple drawn frames -
deliberately NOT an image-generation API, so this works fully offline.
Cards are generated for 1, 4 or 8 words.
"""

from __future__ import annotations

import random

from fpdf import FPDF

from .. import config
from ..engines.base import ModelUnavailable
from .worksheets import DEVA_FONT, OLCHIKI_FONT

CARD_COUNTS = (1, 4, 8)

CARD_COLORS = [
    ("#FFF3E2", "#D96C2F"),
    ("#EAF4EC", "#2F6B4F"),
    ("#FDF0E7", "#C1502E"),
    ("#EEF6F9", "#3D6E7E"),
    ("#F7EFEA", "#8A5A3B"),
    ("#EDF5E8", "#5B7C3A"),
    ("#FBEEE9", "#B75C3E"),
    ("#E9F2F0", "#44695F"),
]


def build_cards(vocabulary: list[dict], count: int) -> list[dict]:
    if count not in CARD_COUNTS:
        raise ValueError(f"card count must be one of {CARD_COUNTS}")
    if not vocabulary:
        raise ModelUnavailable("no vocabulary available for flashcards")
    rng = random.Random(2026)
    pool = list(vocabulary)
    if len(pool) > count:
        pool = rng.sample(pool, count)
    cards = []
    for i, w in enumerate(pool):
        bg, accent = CARD_COLORS[i % len(CARD_COLORS)]
        cards.append(
            {
                "hi": w["hi"],
                "sat": w["sat"],
                "sat_latin": w.get("sat_latin", ""),
                "icon": w.get("icon", ""),
                "category": w.get("category", ""),
                "bg": bg,
                "accent": accent,
            }
        )
    return cards


def render_svg(card: dict, w: int = 320, h: int = 220) -> str:
    icon = card.get("icon") or ""
    icon_size = 64 if icon else 0
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <rect x="4" y="4" width="{w - 8}" height="{h - 8}" rx="18" fill="{card['bg']}" stroke="{card['accent']}" stroke-width="3"/>
  <rect x="4" y="4" width="{w - 8}" height="10" rx="5" fill="{card['accent']}"/>
  <text x="{w / 2}" y="{40 + icon_size}" font-size="{icon_size}" text-anchor="middle">{icon}</text>
  <text x="{w / 2}" y="{h - 92}" font-size="34" text-anchor="middle"
        font-family="'Noto Sans Ol Chiki', sans-serif" fill="#26302B">{card['sat']}</text>
  <text x="{w / 2}" y="{h - 58}" font-size="20" text-anchor="middle"
        font-family="'Noto Sans Devanagari', sans-serif" fill="#5A665E">{card['hi']}</text>
  <text x="{w / 2}" y="{h - 24}" font-size="11" text-anchor="middle"
        font-family="sans-serif" fill="#8B958E">{card['sat_latin'] or 'maatravani card'}</text>
</svg>"""


def render_pdf(cards: list[dict], topic: str = "") -> bytes:
    for p in (DEVA_FONT, OLCHIKI_FONT):
        if not p.exists():
            raise ModelUnavailable(
                f"Flashcard font missing ({p.name}); run scripts/download_models.py"
            )
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_text_shaping(use_shaping_engine=True)
    pdf.add_font("deva", "", str(DEVA_FONT))
    pdf.add_font("olck", "", str(OLCHIKI_FONT))
    pdf.set_auto_page_break(auto=False)

    per_row, per_page = 2, 4
    card_w, card_h = 85, 60
    x0, y0 = (210 - per_row * card_w - (per_row - 1) * 6) / 2, 34

    for page_start in range(0, len(cards), per_page):
        pdf.add_page()
        if topic:
            pdf.set_font("helvetica", size=13)
            pdf.set_text_color(217, 108, 47)
            pdf.cell(0, 8, "MAATRAVANI", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("deva", size=10)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(0, 7, f"Flashcards: {topic}", align="C", new_x="LMARGIN", new_y="NEXT")

        page_cards = cards[page_start:page_start + per_page]
        for idx, card in enumerate(page_cards):
            col, row = idx % per_row, idx // per_row
            x = x0 + col * (card_w + 6)
            y = y0 + row * (card_h + 8)
            pdf.set_draw_color(*_hex_rgb(card["accent"]))
            pdf.set_line_width(0.8)
            pdf.rect(x, y, card_w, card_h)
            pdf.set_font("olck", size=26)
            pdf.set_text_color(38, 48, 43)
            pdf.set_xy(x, y + card_h / 2 - 16)
            pdf.cell(card_w, 14, card["sat"], align="C")
            pdf.set_font("deva", size=14)
            pdf.set_text_color(90, 102, 94)
            pdf.set_xy(x, y + card_h / 2 + 2)
            pdf.cell(card_w, 10, card["hi"], align="C")

    return bytes(pdf.output())


def _hex_rgb(hexc: str) -> tuple:
    hexc = hexc.lstrip("#")
    return tuple(int(hexc[i:i + 2], 16) for i in (0, 2, 4))
