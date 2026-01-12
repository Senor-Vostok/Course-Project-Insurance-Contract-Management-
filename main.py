import sys
from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow
from core.db import db_init


APP_STYLE = """
/* Base */
QWidget {
    font-family: Segoe UI, Arial;
    font-size: 12px;
    color: #1f2937;
    background: #f6f7fb;
}

QMainWindow {
    background: #f6f7fb;
}

/* Cards / panels */
QGroupBox {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    margin-top: 10px;
    padding: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #374151;
    font-weight: 600;
}

/* Labels */
QLabel#Title {
    font-size: 16px;
    font-weight: 700;
    color: #111827;
}
QLabel#Muted {
    color: #6b7280;
}
QLabel#Badge {
    background: #eef2ff;
    border: 1px solid #e0e7ff;
    color: #3730a3;
    padding: 4px 8px;
    border-radius: 999px;
}

/* Inputs */
QComboBox, QLineEdit {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 8px 10px;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox:hover, QLineEdit:hover {
    border-color: #cbd5e1;
}
QComboBox:focus, QLineEdit:focus {
    border-color: #818cf8;
}

/* Buttons */
QPushButton {
    background: #111827;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 9px 12px;
}
QPushButton:hover { background: #0b1220; }
QPushButton:pressed { background: #060b14; }
QPushButton:disabled {
    background: #9ca3af;
    color: #f3f4f6;
}

/* Secondary button */
QPushButton#Secondary {
    background: #ffffff;
    color: #111827;
    border: 1px solid #e5e7eb;
}
QPushButton#Secondary:hover { border-color: #cbd5e1; }
QPushButton#Secondary:pressed { background: #f3f4f6; }

/* Lists */
QListWidget {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 6px;
}
QListWidget::item {
    padding: 10px;
    border-radius: 10px;
}
QListWidget::item:selected {
    background: #111827;
    color: #ffffff;
}
QListWidget::item:hover {
    background: #f3f4f6;
}

/* Message box */
QMessageBox {
    background: #ffffff;
}
"""


def main():
    db_init()
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
