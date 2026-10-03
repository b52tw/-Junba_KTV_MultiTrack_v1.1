from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("峻爸 KTV 多文字軌核對器 v1.1")
    app.setOrganizationName("Junba")
    w = MainWindow(); w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
