from __future__ import annotations

import os
import sys

from PySide6.QtCore import QFile, QTextStream
from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    # Apply QSS
    try:
        from importlib.resources import files
    except Exception:
        files = None
    qss_path = os.path.join(os.path.dirname(__file__), "gui", "style.qss")
    if os.path.exists(qss_path):
        from PySide6.QtCore import QFile
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
