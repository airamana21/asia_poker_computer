from __future__ import annotations

import os
from typing import Dict, Tuple

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from ..core.cards import Card, SUITS, RANKS, JOKER, png_name

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "assets", "cards")
ASSETS_DIR = os.path.normpath(ASSETS_DIR)

CARD_W, CARD_H = 160, 224

SUIT_COLOR = {
    "S": QColor(20, 20, 20),
    "C": QColor(20, 20, 20),
    "H": QColor(200, 20, 20),
    "D": QColor(200, 20, 20),
}
SUIT_GLYPH = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}


def ensure_assets() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)
    # Generate 53 PNGs if missing
    for s in SUITS:
        for r in RANKS:
            _ensure_one(Card(r, s))
    _ensure_one(Card(JOKER, None))


def _ensure_one(card: Card) -> None:
    path = os.path.join(ASSETS_DIR, png_name(card))
    if os.path.exists(path):
        existing = QImage(path)
        if not existing.isNull() and existing.width() == CARD_W and existing.height() == CARD_H:
            return
    img = _render_card(card)
    img.save(path)


def _render_card(card: Card) -> QImage:
    img = QImage(CARD_W, CARD_H, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(img)
    painter.fillRect(0, 0, CARD_W, CARD_H, QColor(245, 245, 245))
    pen = QPen(QColor(30, 30, 30))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.drawRect(1, 1, CARD_W - 2, CARD_H - 2)

    if card.rank == JOKER:
        painter.setPen(QPen(QColor(40, 40, 120)))
        font = QFont("Segoe UI", 24, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRect(0, 40, CARD_W, 60), Qt.AlignmentFlag.AlignCenter, "JOKER")
    else:
        # Corner rank and suit
        color = SUIT_COLOR[card.suit]  # type: ignore[index]
        painter.setPen(QPen(color))
        painter.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        painter.drawText(8, 24, card.rank)
        painter.setFont(QFont("Segoe UI Symbol", 18))
        painter.drawText(8, 44, SUIT_GLYPH[card.suit])  # type: ignore[index]
        # Center glyph
        painter.setFont(QFont("Segoe UI Symbol", 60))
        painter.drawText(QRect(0, 40, CARD_W, 90), Qt.AlignmentFlag.AlignCenter, SUIT_GLYPH[card.suit])  # type: ignore[index]

    painter.end()
    return img


def asset_path(card: Card) -> str:
    return os.path.join(ASSETS_DIR, png_name(card))
