#!/usr/bin/env python3
"""Пример: ретроспектива спринта на три команды.

Один кадр 16:9 на команду, задание продублировано в каждом — участник открывает
свой кадр во весь экран и видит всё, что нужно для шага.

    python examples/retro.py
    python scripts/validate.py retro.holst
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from holst import Board, fit_scale, BLUE, GREEN, RED, WHITE   # noqa: E402

W, H, PAD = 4800, 2700, 200
STEP_X, STEP_Y = W + 450, H + 900

COLUMNS = [("Мешало", RED), ("Помогало", GREEN), ("Попробуем", BLUE)]
TASK = "Один стикер — одна мысль. 10 минут, потом читаем вслух"


def slide(b, col, row, title, task=None):
    """Кадр 16:9: заголовок + задание + рабочая область под ними.

    Возвращает (кадр, x, y) — где y уже сдвинут под шапку.
    """
    x, y = col * STEP_X, row * STEP_Y
    f = b.slide(x, y, title)

    ts = fit_scale(title, W - 2 * PAD, 285, 12.0, floor=6.0)
    b.text(x + PAD, y + 110, title, scale=ts, width=int((W - 2 * PAD) / ts),
           color=0x6B6B6B, bold=True, halign="center", fixed_width=True, parent=f)

    if task:
        sc = fit_scale(task, W - 2 * PAD - 400, 235, 5.0, floor=3.2)
        b.text(x + PAD + 200, y + 420, task, scale=sc,
               width=int((W - 2 * PAD - 400) / sc), color=0x5A5A5A,
               halign="center", fixed_width=True, parent=f)

    return f, x, y + (700 if task else 430)


def main():
    b = Board("Ретроспектива спринта")

    for i in (1, 2, 3):
        f, x, y = slide(b, i - 1, 0,
                        "Что мешало нам в спринте  ·  Команда %d" % i, TASK)
        cw = (W - 2 * PAD - 2 * 60) / 3
        for j, (name, color) in enumerate(COLUMNS):
            dx = x + PAD + j * (cw + 60)
            b.shape(dx, y, cw, 190, name, fill=color, stroke=color,
                    font_size=90, parent=f)
            b.shape(dx, y + 190, cw, 1400, fill=WHITE, stroke=0xBFBFBF, parent=f)
            b.empty_grid(dx + 40, y + 240, 2, 2, cw - 80, 1300, color=color, parent=f)

    out = b.save("retro.holst")
    print("Готово:", out, "—", len(b.objects), "объектов")


if __name__ == "__main__":
    main()
