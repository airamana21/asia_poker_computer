from __future__ import annotations

import os
from typing import List, Optional

from PySide6.QtCore import Qt, QSettings, QSize, QThread, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)

from ..core.cards import Card, parse
from ..core.evaluator import evaluate_best_setup
from .assets import ensure_assets, CARD_W, CARD_H
from .card_selector import CardSelector, grid_natural_size
from .selected_status_bar import SelectedStatusBar
from .results_panel import ResultsPanel
from .workers import SimWorker

# ── Design constants ──────────────────────────────────────────
# Natural grid size at scale = 1.0
_GRID_NAT_W, _GRID_NAT_H = grid_natural_size()

# The left panel (card grid) takes this fraction of the total width
_LEFT_FRAC = 0.65

# Status bar height at scale = 1.0
_STATUS_NAT_H = int(CARD_H * 0.9) + 20

# Full design size at scale = 1.0
_DESIGN_W = int(_GRID_NAT_W / _LEFT_FRAC)     # ~3446
_DESIGN_H = _STATUS_NAT_H + _GRID_NAT_H       # ~1389

# Locked aspect ratio
_ASPECT = _DESIGN_W / _DESIGN_H

# Default startup width and scale limits
_DEFAULT_WIDTH = 1600
_MIN_SCALE = 0.25
_MAX_SCALE = 2.0


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asia Poker 4\u20112\u20111 Assistant")
        ensure_assets()

        self.settings = QSettings("asia_poker_computer", "app")

        self._scale = 0.0       # force first apply
        self._programmatic_resize = False   # flag for aspect ratio corrections
        
        # Timer to debounce scale updates during resize
        self._scale_update_timer = QTimer()
        self._scale_update_timer.setSingleShot(True)
        self._scale_update_timer.setInterval(10)
        self._scale_update_timer.timeout.connect(self._apply_scale)
        
        # Timer to enforce aspect ratio only AFTER resize completes
        self._aspect_correction_timer = QTimer()
        self._aspect_correction_timer.setSingleShot(True)
        self._aspect_correction_timer.setInterval(150)  # Wait 150ms after last resize
        self._aspect_correction_timer.timeout.connect(self._enforce_aspect_ratio)
        
        # Track last resize dimensions for aspect ratio correction
        self._last_resize_w = 0
        self._last_resize_h = 0

        # State
        self.selected: List[Card] = []
        self.thread: QThread | None = None
        self.worker: SimWorker | None = None

        # ── Build UI ────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Row 1: Selected cards status bar ──
        self.status_bar = SelectedStatusBar(
            on_slot_clicked=self.on_slot_clicked)
        root.addWidget(self.status_bar)

        # ── Row 2: Splitter — card grid (left) | controls + results (right) ──
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # Left: card selector
        self.selector = CardSelector(on_card_clicked=self.on_card_clicked)
        self.splitter.addWidget(self.selector)

        # Right: controls + results
        rbox = QWidget()
        rlay = QVBoxLayout(rbox)
        rlay.setContentsMargins(4, 4, 4, 4)

        controls = QHBoxLayout()
        self.btn_recommend = QPushButton("Recommend")
        self.btn_recommend.setEnabled(False)
        self.btn_recommend.clicked.connect(self.on_recommend)
        controls.addWidget(self.btn_recommend)

        self.samples = QSlider(Qt.Orientation.Horizontal)
        self.samples.setMinimum(10_000)
        self.samples.setMaximum(500_000)
        self.samples.setSingleStep(10_000)
        self.samples.setValue(int(self.settings.value("samples", 100_000)))
        controls.addWidget(QLabel("Samples"))
        controls.addWidget(self.samples)
        self.lbl_samples = QLabel(str(self.samples.value()))
        self.samples.valueChanged.connect(
            lambda val: self.lbl_samples.setText(str(val)))
        controls.addWidget(self.lbl_samples)

        self.btn_new = QPushButton("New Hand")
        self.btn_new.clicked.connect(self.on_new_hand)
        controls.addWidget(self.btn_new)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        controls.addWidget(self.progress)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.on_cancel)
        controls.addWidget(self.btn_cancel)

        rlay.addLayout(controls)
        self.results = ResultsPanel()
        rlay.addWidget(self.results, 1)

        self.splitter.addWidget(rbox)
        root.addWidget(self.splitter, 1)

        # ── Window size ──
        saved = self.settings.value("window_size")
        if isinstance(saved, QSize) and saved.width() > 200:
            w = saved.width()
            h = int(w / _ASPECT)
            self.resize(w, h)
        else:
            self.resize(_DEFAULT_WIDTH, int(_DEFAULT_WIDTH / _ASPECT))

        # Minimum window size (scale ~0.25)
        min_w = max(400, int(_DESIGN_W * _MIN_SCALE))
        min_h = int(min_w / _ASPECT)
        self.setMinimumSize(min_w, min_h)

        # Deferred init: set splitter sizes and initial scale
        QTimer.singleShot(0, self._deferred_init)

        self.refresh_ui()

    def _deferred_init(self):
        """Set splitter proportions and apply initial scale after show."""
        total = self.splitter.width()
        left = int(total * _LEFT_FRAC)
        self.splitter.setSizes([left, total - left])
        # Lock splitter: make it non-interactive so aspect ratio stays clean
        self.splitter.setHandleWidth(0)
        self._apply_scale()

    # ── Scaling ─────────────────────────────────────────────

    def _apply_scale(self):
        """Compute scale from left panel width / grid natural width."""
        left_w = self.splitter.sizes()[0] if self.splitter.sizes() else int(
            self.width() * _LEFT_FRAC)
        scale = left_w / _GRID_NAT_W
        scale = max(_MIN_SCALE, min(_MAX_SCALE, scale))

        if abs(scale - self._scale) < 0.005:
            return
        self._scale = scale
        self.selector.set_scale(scale)
        self.status_bar.set_scale(scale)
        self.results.set_scale(scale)

    # ── UI helpers ──────────────────────────────────────────

    def refresh_ui(self):
        slots = self.selected + [None] * (7 - len(self.selected))
        self.status_bar.set_cards(slots)
        self.selector.set_disabled([c.id() for c in self.selected])
        self.btn_recommend.setEnabled(
            len(self.selected) == 7 and not self.thread)
        self.btn_new.setEnabled(self.thread is None)

    def on_card_clicked(self, card: Card):
        if card in self.selected:
            return
        if len(self.selected) < 7:
            self.selected.append(card)
            self.refresh_ui()

    def on_slot_clicked(self, idx: int):
        if self.thread:
            return
        if idx < len(self.selected):
            del self.selected[idx]
            self.refresh_ui()

    def on_new_hand(self):
        if self.thread:
            return
        self.selected.clear()
        self.results.clear_results()
        self.refresh_ui()

    # ── Simulation ─────────────────────────────────────────

    def on_recommend(self):
        if len(self.selected) != 7 or self.thread:
            return
        self.results.clear_results()
        self.settings.setValue("samples", int(self.samples.value()))

        self.thread = QThread()
        self.worker = SimWorker(
            self.selected, samples=int(self.samples.value()))
        self.worker.moveToThread(self.thread)
        self.worker.progress.connect(self.on_sim_progress)
        self.worker.finished.connect(self.on_sim_finished)
        self.worker.canceled.connect(self.on_sim_canceled)
        self.worker.error.connect(self.on_sim_error)
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)

        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.btn_cancel.setEnabled(True)
        self.refresh_ui()
        self.thread.start()

    def on_cancel(self):
        if self.worker:
            self.worker.cancel()

    def on_sim_progress(self, f: float):
        self.progress.setValue(max(0, min(100, int(f * 100))))

    def _cleanup_thread(self):
        self.btn_cancel.setEnabled(False)
        self.progress.setVisible(False)
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.thread = None
        self.worker = None
        self.refresh_ui()

    def on_sim_finished(self, best, all_results):
        bp = best.rp
        self.results.show_result(
            "Best", bp.hi, bp.mid, bp.low, best.win_rate)
        for alt in all_results[1:4]:
            rp = alt.rp
            self.results.show_result(
                "Alt", rp.hi, rp.mid, rp.low, alt.win_rate)
        self._cleanup_thread()

    def on_sim_canceled(self):
        QMessageBox.information(self, "Canceled", "Simulation canceled")
        self._cleanup_thread()

    def on_sim_error(self, msg: str):
        QMessageBox.critical(self, "Error", msg)
        self._cleanup_thread()

    # ── Events ──────────────────────────────────────────────

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        
        # Skip processing if this is our own programmatic resize
        if self._programmatic_resize:
            self._programmatic_resize = False
            return
        
        new_w = event.size().width()
        new_h = event.size().height()
        
        # Store dimensions for later aspect ratio correction
        self._last_resize_w = new_w
        self._last_resize_h = new_h
        
        # Update layout elements immediately for smooth visual feedback
        self._update_layout()
        
        # Restart the aspect correction timer
        # This means we only enforce aspect ratio 150ms after the user stops resizing
        self._aspect_correction_timer.start()
    
    def _enforce_aspect_ratio(self):
        """
        Enforce aspect ratio after resize completes (debounced).
        This is called 150ms after the last resize event.
        """
        w = self._last_resize_w
        h = self._last_resize_h
        
        if w <= 0 or h <= 0:
            return
        
        # Calculate expected dimensions for aspect ratio
        expected_h = round(w / _ASPECT)
        expected_w = round(h * _ASPECT)
        
        # Determine which dimension to base the correction on
        dw = abs(w - self.width())
        dh = abs(h - self.height())
        
        # Use a tolerance to avoid unnecessary tiny corrections
        TOLERANCE = 2
        
        target_w, target_h = w, h
        needs_correction = False
        
        if dw >= dh:
            # Width was changed more → adjust height
            if abs(expected_h - h) > TOLERANCE:
                target_h = expected_h
                needs_correction = True
        else:
            # Height was changed more → adjust width
            if abs(expected_w - w) > TOLERANCE:
                target_w = expected_w
                needs_correction = True
        
        if needs_correction:
            self._programmatic_resize = True
            self.resize(target_w, target_h)
    
    def _update_layout(self):
        """Update splitter proportions and scale without triggering resize."""
        # Update splitter proportions
        total = self.splitter.width()
        if total > 0:
            left = int(total * _LEFT_FRAC)
            self.splitter.setSizes([left, total - left])
        
        # Debounce scale updates using timer to avoid excessive recalculations
        if not self._scale_update_timer.isActive():
            self._scale_update_timer.start()

    def closeEvent(self, event):  # type: ignore[override]
        self.settings.setValue(
            "window_size", QSize(self.width(), self.height()))
        super().closeEvent(event)
