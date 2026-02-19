from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal, QSize, QEvent
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QGraphicsDropShadowEffect

from ..core.cards import Card, JOKER
from .assets import asset_path, CARD_W, CARD_H

_HOVER_SCALE = 1.07  # 7% scale-up on hover


class ClickableLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event):  # type: ignore[override]
        self.clicked.emit()
        return super().mouseReleaseEvent(event)


class SelectedStatusBar(QFrame):
    def __init__(self, on_slot_clicked: Callable[[int], None]):
        super().__init__()
        self.on_slot_clicked = on_slot_clicked
        self.setObjectName("SelectedStatusBar")
        self.setFrameShape(QFrame.Shape.Box)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
        self._layout = layout
        self._base_margins = layout.contentsMargins()
        self._base_spacing = layout.spacing()
        self._scale = 0.0  # force first set_scale to apply
        self._cards: List[Optional[Card]] = [None] * 7
        self.slots: List[ClickableLabel] = []
        self._slot_size: QSize = QSize(0, 0)
        
        for i in range(7):
            lbl = ClickableLabel()
            lbl.setStyleSheet("background: #eee; border: 1px dashed #999;")
            lbl.setScaledContents(True)
            lbl.clicked.connect(lambda i=i: self.on_slot_clicked(i))
            lbl.setAttribute(Qt.WidgetAttribute.WA_Hover)  # Enable hover events
            lbl.installEventFilter(self)  # Install event filter for hover effects
            layout.addWidget(lbl)
            self.slots.append(lbl)
        self.set_scale(1.0)

    def set_cards(self, cards: List[Optional[Card]]):
        for idx in range(7):
            self._cards[idx] = cards[idx] if idx < len(cards) else None
        self._refresh_pixmaps()

    def set_scale(self, scale: float):
        if abs(scale - self._scale) < 1e-3:
            return
        # Clean up any active hover before changing scale
        for lbl in self.slots:
            self._remove_hover(lbl)
        self._scale = scale
        margins = self._base_margins
        self._layout.setContentsMargins(
            int(margins.left() * scale),
            int(margins.top() * scale),
            int(margins.right() * scale),
            int(margins.bottom() * scale),
        )
        self._layout.setSpacing(int(self._base_spacing * scale))
        
        self._slot_size = QSize(int(CARD_W * 0.9 * scale), int(CARD_H * 0.9 * scale))
        for lbl in self.slots:
            lbl.setFixedSize(self._slot_size)
        self._refresh_pixmaps()

    def _refresh_pixmaps(self):
        for lbl, card in zip(self.slots, self._cards):
            if card is None:
                lbl.clear()
                lbl.setToolTip("")
                self._remove_hover(lbl)
            else:
                pix = QPixmap(asset_path(card))
                lbl.setPixmap(
                    pix.scaled(
                        lbl.width(),
                        lbl.height(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                lbl.setToolTip(card.id())

    # ── Hover helpers ──────────────────────────────────────

    def _apply_hover(self, lbl: ClickableLabel):
        """Apply scale-up + glow to a status bar slot without affecting layout."""
        layout = self._layout

        # Save original state
        lbl._hover_orig_geom = lbl.geometry()

        # Freeze layout so other slots stay put
        layout.setEnabled(False)

        # Bring on top
        lbl.raise_()

        # Compute scaled geometry centred on the original centre
        og = lbl._hover_orig_geom
        nw = int(og.width() * _HOVER_SCALE)
        nh = int(og.height() * _HOVER_SCALE)
        cx, cy = og.center().x(), og.center().y()

        # Relax fixed-size constraints
        lbl.setMinimumSize(0, 0)
        lbl.setMaximumSize(16777215, 16777215)
        lbl.setGeometry(cx - nw // 2, cy - nh // 2, nw, nh)

        # Re-scale the pixmap to the new size
        idx = self.slots.index(lbl)
        card = self._cards[idx]
        if card is not None:
            pix = QPixmap(asset_path(card))
            lbl.setPixmap(
                pix.scaled(
                    nw, nh,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        # Orange glow
        shadow = QGraphicsDropShadowEffect(lbl)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(255, 87, 34, 255))
        shadow.setOffset(0, 0)
        lbl.setGraphicsEffect(shadow)

    def _remove_hover(self, lbl: ClickableLabel):
        """Restore a slot to its normal size and re-enable layout."""
        if not hasattr(lbl, '_hover_orig_geom'):
            lbl.setGraphicsEffect(None)
            return

        og = lbl._hover_orig_geom

        # Restore original fixed size and position
        lbl.setFixedSize(og.size())
        lbl.setGeometry(og)
        lbl.setGraphicsEffect(None)

        # Re-scale pixmap back to normal size
        idx = self.slots.index(lbl)
        card = self._cards[idx]
        if card is not None:
            pix = QPixmap(asset_path(card))
            lbl.setPixmap(
                pix.scaled(
                    og.width(), og.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        del lbl._hover_orig_geom

        # Re-enable layout
        self._layout.setEnabled(True)
    
    def eventFilter(self, obj, event):
        """Handle hover events for status bar slots."""
        if isinstance(obj, ClickableLabel) and obj in self.slots:
            idx = self.slots.index(obj)
            
            # Only apply hover effect to filled slots
            if self._cards[idx] is not None:
                if event.type() == QEvent.Type.Enter:
                    self._apply_hover(obj)
                    
                elif event.type() == QEvent.Type.Leave:
                    self._remove_hover(obj)
        
        return super().eventFilter(obj, event)
