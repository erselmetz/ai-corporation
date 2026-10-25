"""Visible, synthetic renderer benchmark only; never application Brain data."""
import argparse
import json
import math
from pathlib import Path
import time


def points(count, angle):
    for index in range(count):
        z = 1 - 2 * (index + .5) / count
        radius = math.sqrt(1 - z * z)
        phase = index * 2.399963229728653
        x, y = math.cos(phase) * radius, math.sin(phase) * radius
        yield x * math.cos(angle) + z * math.sin(angle), y, z * math.cos(angle) - x * math.sin(angle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--toolkit', choices=['qt', 'tk'], required=True)
    parser.add_argument('--nodes', type=int, choices=[300, 2000], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import QTimer, QPointF
    from PySide6.QtGui import QPainter, QColor, QRadialGradient
    app = QApplication([])
    frames = []
    started = time.perf_counter()
    previous = started
    if args.toolkit == 'qt':
        class View(QWidget):
            def paintEvent(self, event):
                nonlocal previous
                now = time.perf_counter()
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.fillRect(self.rect(), QColor('#100e0a'))
                for x, y, z in points(args.nodes, (now - started) * .2):
                    center = QPointF(440 + x * 280, 340 + y * 280)
                    radius = 3 + (z + 1) * 1.5
                    glow = QRadialGradient(center, radius * 3)
                    glow.setColorAt(0, QColor(255, 197, 75, 210))
                    glow.setColorAt(.35, QColor(237, 185, 78, 120))
                    glow.setColorAt(1, QColor(237, 185, 78, 0))
                    painter.setPen(QColor(0, 0, 0, 0)); painter.setBrush(glow)
                    painter.drawEllipse(center, radius * 3, radius * 3)
                painter.end()
                frames.append(now - previous); previous = now
        view = View(); view.resize(880, 680); view.setWindowTitle('Synthetic Qt Brain benchmark'); view.show()
        timer = QTimer(); timer.timeout.connect(view.update); timer.start(0)
        def finish():
            timer.stop(); view.grab().save(str(args.output / f'qt-{args.nodes}.png')); app.quit()
        QTimer.singleShot(4500, finish)
        app.exec()
    else:
        import customtkinter as ctk
        import tkinter as tk
        window = ctk.CTk(); window.title('Synthetic Tk Canvas Brain benchmark'); window.geometry('880x680')
        canvas = tk.Canvas(window, width=880, height=680, bg='#100e0a', highlightthickness=0); canvas.pack(fill='both', expand=True)
        items = [[canvas.create_oval(0, 0, 0, 0, outline='', fill=color) for color in ['#302413', '#77501e', '#edb94e']] for _ in range(args.nodes)]
        def draw():
            nonlocal previous
            now = time.perf_counter()
            for group, (x, y, z) in zip(items, points(args.nodes, (now - started) * .2)):
                cx, cy = 440 + x * 280, 340 + y * 280
                radius = 3 + (z + 1) * 1.5
                for item, factor in zip(group, [3, 1.8, .7]):
                    r = radius * factor; canvas.coords(item, cx-r, cy-r, cx+r, cy+r)
            frames.append(now - previous); previous = now
            if now - started < 4.5: window.after(1, draw)
            else:
                app.primaryScreen().grabWindow(0, window.winfo_rootx(), window.winfo_rooty(), window.winfo_width(), window.winfo_height()).save(str(args.output / f'tk-{args.nodes}.png'))
                window.destroy()
        window.after(100, draw); window.mainloop()
    elapsed = time.perf_counter() - started
    measured = frames[10:]  # discard startup frames
    result = {'toolkit': args.toolkit, 'nodes': args.nodes, 'frames': len(frames), 'wall_seconds': round(elapsed, 3),
              'repaint_fps': round(len(measured) / sum(measured), 2), 'mean_frame_ms': round(sum(measured) / len(measured) * 1000, 2),
              'p95_frame_ms': round(sorted(measured)[int(len(measured)*.95)] * 1000, 2),
              'kind': 'Visible synthetic CPU projected-3D repaint throughput, not GPU/display-present FPS',
              'dimensions': [880, 680], 'qt_platform': app.platformName(), 'dpr': app.primaryScreen().devicePixelRatio()}
    (args.output / f'{args.toolkit}-{args.nodes}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__': main()
