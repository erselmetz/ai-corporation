"""Shared Aurora design tokens for the native ERSELMETZ AI workspace."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Tokens:
    background: str = '#070B18'
    background_raised: str = '#0B1224'
    panel: str = '#111A31'
    panel_hover: str = '#172443'
    aurora_cyan: str = '#52E5FF'
    aurora_blue: str = '#6C8CFF'
    aurora_violet: str = '#B36CFF'
    aurora_green: str = '#5EF2C2'
    gold: str = '#52E5FF'
    light_gold: str = '#2859B8'
    text: str = '#F4F7FF'
    muted: str = '#A9B6D3'
    border: str = '#2A3A60'
    danger: str = '#FF6B86'
    space: int = 8
    radius: int = 12
    font: str = 'Segoe UI Variable'
    motion_ms: int = 160


TOKENS = Tokens()


def apply_theme(app, light=False):
    t=TOKENS
    if light:
        bg='#EEF4FF';raised='#F7FAFF';panel='#FFFFFF';hover='#E7EEFF';text='#14203A';muted='#52617F';border='#B8C7E6';accent='#2859B8';violet='#7144C7';green='#087F69'
        aurora='qradialgradient(cx:0.18, cy:0.08, radius:0.92, fx:0.18, fy:0.08, stop:0 #D8F7FF, stop:0.34 #EEF1FF, stop:0.72 #F5ECFF, stop:1 #EEF4FF)'
    else:
        bg=t.background;raised=t.background_raised;panel=t.panel;hover=t.panel_hover;text=t.text;muted=t.muted;border=t.border;accent=t.aurora_cyan;violet=t.aurora_violet;green=t.aurora_green
        aurora='qradialgradient(cx:0.18, cy:0.02, radius:1.05, fx:0.18, fy:0.02, stop:0 #173B62, stop:0.28 #101B3A, stop:0.58 #17132F, stop:1 #070B18)'
    app.setStyleSheet(f'''
        QWidget {{ background: {bg}; color: {text}; font-family: "{t.font}", "Segoe UI"; font-size: 14px; selection-background-color: {violet}; selection-color: #FFFFFF; }}
        QMainWindow, QWidget#auroraRoot {{ background: {aurora}; }}
        QWidget#auroraPane, QFrame#panel, QDialog {{ background: {panel}; border: 1px solid {border}; border-radius: {t.radius}px; }}
        QScrollArea, QScrollArea > QWidget > QWidget, QAbstractScrollArea::viewport {{ background: transparent; border: none; }}
        QLabel, QCheckBox, QRadioButton {{ background: transparent; border: none; }}
        QLabel#muted {{ color: {muted}; }}
        QPushButton, QComboBox, QSpinBox, QLineEdit {{ background: {panel}; border: 1px solid {border}; border-radius: {t.radius}px; padding: 8px 12px; min-height: 22px; }}
        QPushButton:hover, QComboBox:hover, QSpinBox:hover {{ background: {hover}; border-color: {accent}; }}
        QPushButton#primaryAction {{ background: {accent}; color: #07101F; border: 1px solid {accent}; font-size: 16px; font-weight: 700; padding: 12px 18px; }}
        QPushButton#primaryAction:hover {{ background: {green}; border-color: {green}; }}
        QPushButton:pressed {{ background: {border}; }}
        QPushButton:focus, QComboBox:focus, QPlainTextEdit:focus, QTextBrowser:focus, QListWidget:focus, QSpinBox:focus, QLineEdit:focus {{ border: 2px solid {accent}; }}
        QCheckBox:focus, QRadioButton:focus {{ color: {accent}; }}
        QPushButton:disabled, QComboBox:disabled {{ color: {muted}; border-color: {border}; background: {raised}; }}
        QPlainTextEdit, QTextBrowser, QListWidget, QTreeWidget, QTableWidget {{ background: {raised}; border: 1px solid {border}; border-radius: {t.radius}px; padding: 10px; alternate-background-color: {panel}; }}
        QListWidget::item, QTreeWidget::item {{ border-radius: 7px; padding: 6px; }}
        QListWidget::item:hover, QTreeWidget::item:hover {{ background: {hover}; }}
        QListWidget::item:selected, QTreeWidget::item:selected {{ background: {border}; color: {text}; }}
        QSplitter::handle {{ background: transparent; width: 8px; height: 8px; }}
        QSplitter::handle:hover {{ background: {accent}; }}
        QTabWidget::pane {{ border: 1px solid {border}; border-radius: {t.radius}px; background: {raised}; top: -1px; }}
        QTabBar::tab {{ background: transparent; color: {muted}; padding: 9px 16px; margin-right: 3px; border-bottom: 2px solid transparent; }}
        QTabBar::tab:hover {{ color: {text}; }}
        QTabBar::tab:selected {{ color: {accent}; border-bottom: 2px solid {accent}; }}
        QCheckBox {{ spacing: 9px; color: {text}; }}
        QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {border}; border-radius: 5px; background: {raised}; }}
        QCheckBox::indicator:hover {{ border-color: {accent}; }}
        QCheckBox::indicator:checked {{ background: {green}; border-color: {green}; }}
        QMenu {{ background: {panel}; border: 1px solid {border}; border-radius: 10px; padding: 6px; }}
        QMenu::item {{ padding: 8px 24px; border-radius: 7px; }}
        QMenu::item:selected {{ background: {hover}; color: {accent}; }}
        QToolTip {{ background: {panel}; color: {text}; border: 1px solid {accent}; padding: 6px; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {border}; min-height: 28px; border-radius: 5px; }}
        QScrollBar::handle:vertical:hover {{ background: {accent}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QProgressBar {{ background: {raised}; border: 1px solid {border}; border-radius: 7px; text-align: center; }}
        QProgressBar::chunk {{ background: {green}; border-radius: 6px; }}
    ''')
