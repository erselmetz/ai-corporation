"""Shared palette, spacing, type, radius and motion tokens for native widgets."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Tokens:
    background: str = '#100e0a'
    panel: str = '#1c1811'
    gold: str = '#edb94e'
    light_gold: str = '#805800'
    text: str = '#f4e9cf'
    muted: str = '#c5b99d'
    border: str = '#756341'
    space: int = 8
    radius: int = 8
    font: str = 'Segoe UI'
    motion_ms: int = 160


TOKENS = Tokens()


def apply_theme(app, light=False):
    t = TOKENS
    bg, panel, text, border = ('#faf4e5', '#eee4cf', '#211b12', '#756341') if light else (t.background, t.panel, t.text, t.border)
    accent = t.light_gold if light else t.gold
    app.setStyleSheet(f'''
        QWidget {{ background: {bg}; color: {text}; font-family: "{t.font}"; font-size: 14px; }}
        QFrame#panel, QDialog {{ background: {panel}; }}
        QLabel, QCheckBox {{ background: transparent; }}
        QPushButton, QComboBox, QSpinBox {{ background: {panel}; border: 1px solid {border}; border-radius: {t.radius}px; padding: 8px 12px; min-height: 20px; }}
        QPushButton:hover {{ border-color: {accent}; }}
        QPushButton:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus, QSpinBox:focus {{ border: 2px solid {accent}; }}
        QCheckBox:focus {{ border: 2px solid {accent}; }}
        QPushButton:disabled {{ color: {border}; }}
        QPlainTextEdit, QTextBrowser, QListWidget {{ border: 1px solid {border}; border-radius: {t.radius}px; padding: 8px; }}
        QSplitter::handle {{ background: {border}; width: 5px; }}
        QTabBar::tab {{ padding: 8px 16px; }}
        QTabBar::tab:selected {{ color: {accent}; border-bottom: 2px solid {accent}; }}
        QCheckBox {{ spacing: 8px; }}
    ''')
