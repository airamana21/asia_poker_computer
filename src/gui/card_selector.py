from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFrame, QGridLayout, QPushButton, QSizePolicy,
                               QWidget)

from ..core.cards import Card, SUITS, RANKS, JOKER
from .assets import asset_path, CARD_W, CARD_H

# Number of columns (ranks) and rows (suits + joker)
_COLS = len(RANKS)   # 13
_ROWS = len(SUITS) + 1  # 5 (4 suits + joker row)

# Layout constants at scale=1.0
_BTN_RATIO = 1.05
_ICON_RATIO = 0.95
_JOKER_BTN_RATIO = 0.9
_JOKER_ICON_RATIO = 0.75
_GRID_SPACING = 4
_GRID_MARGIN = 4


def grid_natural_size() -> Tuple[int, int]:
    """Return (width, height) of the card grid at scale = 1.0."""
    btn_w = int(CARD_W * _BTN_RATIO)
    btn_h = int(CARD_H * _BTN_RATIO)
    # Joker row is one button spanning all columns, height driven by joker ratio
    joker_h = int(CARD_H * _JOKER_BTN_RATIO)
    w = _COLS * btn_w + (_COLS - 1) * _GRID_SPACING + 2 * _GRID_MARGIN
    h = (len(SUITS) * btn_h + joker_h
         + _ROWS * _GRID_SPACING   # spacing between rows (approx)
         + 2 * _GRID_MARGIN)
    return w, h


class CardSelector(QFrame):
    def __init__(self, on_card_clicked: Callable[[Card], None]):
        super().__init__()
        self.on_card_clicked = on_card_clicked
        self.setObjectName("CardSelector")
        layout = QGridLayout(self)
        layout.setContentsMargins(_GRID_MARGIN, _GRID_MARGIN,
                                  _GRID_MARGIN, _GRID_MARGIN)
        layout.setSpacing(_GRID_SPACING)
        self.buttons: Dict[str, QPushButton] = {}
        self._scale = 0.0  # force first set_scale to apply
        self._joker_id: str | None = None

        # Grid by suit rows, rank columns, plus a Joker button at the end
        for row, suit in enumerate(SUITS):
            for col, rank in enumerate(RANKS):
                card = Card(rank, suit)
                btn = QPushButton()
                btn.setIcon(QIcon(asset_path(card)))
                btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                                  QSizePolicy.Policy.Fixed)
                btn.clicked.connect(
                    lambda _=False, c=card: self.on_card_clicked(c))
                btn.setToolTip(card.id())
                layout.addWidget(btn, row, col)
                self.buttons[card.id()] = btn
        # Joker button
        j = Card(JOKER, None)
        jbtn = QPushButton()
        jbtn.setIcon(QIcon(asset_path(j)))
        jbtn.setSizePolicy(QSizePolicy.Policy.Fixed,
                           QSizePolicy.Policy.Fixed)
        jbtn.clicked.connect(lambda _=False, c=j: self.on_card_clicked(c))
        jbtn.setToolTip(j.id())
        layout.addWidget(jbtn, len(SUITS), 0, 1, _COLS)
        self.buttons[j.id()] = jbtn
        self._joker_id = j.id()

        # Apply initial scale
        self.set_scale(1.0)

    def _apply_sizes(self, btn: QPushButton, icon_ratio: float,
                     button_ratio: float):
        iw = int(CARD_W * icon_ratio * self._scale)
        ih = int(CARD_H * icon_ratio * self._scale)
        bw = int(CARD_W * button_ratio * self._scale)
        bh = int(CARD_H * button_ratio * self._scale)
        btn.setIconSize(QSize(max(1, iw), max(1, ih)))
        btn.setFixedSize(max(1, bw), max(1, bh))

    def set_scale(self, scale: float):
        if abs(scale - self._scale) < 1e-3:
            return
        self._scale = scale
        # Update layout spacing/margins proportionally
        lay = self.layout()
        if lay:
            lay.setSpacing(max(1, int(_GRID_SPACING * scale)))
            m = max(1, int(_GRID_MARGIN * scale))
            lay.setContentsMargins(m, m, m, m)
        for card_id, btn in self.buttons.items():
            if card_id == self._joker_id:
                self._apply_sizes(btn, _JOKER_ICON_RATIO, _JOKER_BTN_RATIO)
            else:
                self._apply_sizes(btn, _ICON_RATIO, _BTN_RATIO)
        self.updateGeometry()

    def set_disabled(self, ids: List[str]):
        for k, b in self.buttons.items():
            b.setEnabled(k not in ids)
