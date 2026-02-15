from __future__ import annotations

import multiprocessing
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtCore import QFile, QTextStream
from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow
from src.utils.resources import get_resource_path


def main():
    # Required for multiprocessing support in frozen executables
    multiprocessing.freeze_support()
    
    app = QApplication(sys.argv)
    
    # Apply QSS using resource path helper
    qss_path = get_resource_path("src/gui/style.qss")
    if os.path.exists(qss_path):
        f = QFile(qss_path)
        if f.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            app.setStyleSheet(str(QTextStream(f).readAll()))
            f.close()

    w = MainWindow()
    w.resize(1100, 700)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
