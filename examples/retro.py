#!/usr/bin/env python3
"""Пример: ретроспектива спринта на три команды.

Один кадр 16:9 на команду, задание продублировано в каждом — участник открывает
свой кадр во весь экран и видит всё, что нужно для шага.

Показывает курсорный API: заголовок, задание и колонки встают друг под другом
сами, без ручного расчёта координат.

    python examples/retro.py
    python scripts/validate.py retro.holst
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from holst import Board, box_h, BLUE, GREEN, RED, WHITE   # noqa: E402

COLUMNS = [("Мешало", RED), ("Помогало", GREEN), ("Попробуем", BLUE)]
TASK = "Один стикер — одна мысль. 10 минут, потом читаем вслух"


def main():
    b = Board("Ретроспектива спринта")

    # Строка 1: по кадру на команду, задание продублировано.
    for i in (1, 2, 3):
        s = b.page("Что мешало нам в спринте · Команда %d" % i)
        s.title("Что мешало нам в спринте  ·  Команда %d" % i, halign="center")
        s.body(TASK, halign="center", width=s.content_w)
        s.gap(60)

        head_h = max(box_h(name, w, 90, minimum=190)
                     for (name, _), (_, w) in zip(COLUMNS, s.columns(3)))
        top = s.cursor
        for (name, color), (x, w) in zip(COLUMNS, s.columns(3)):
            s.shape(x, top, w, head_h, name, fill=color, stroke=color,
                    font_size=90, grow=False)
            s.shape(x, top + head_h, w, s.bottom - top - head_h,
                    fill=WHITE, stroke=0xBFBFBF)
            s.sticker_grid([""] * 4, cols=2, color=color, width=w - 80,
                           x=x + 40, y=top + head_h + 50,
                           box_h_=s.bottom - top - head_h - 100)

    # Строка 2: сведение результатов.
    b.new_row()
    s = b.page("Что забираем в следующий спринт")
    s.title("Что забираем в следующий спринт")
    s.body("**Одно решение — один стикер.** Формулируйте так, чтобы у него "
           "нашёлся хозяин: {red10|«кто и когда»}, а не «надо бы».")
    s.bullets(["что перестаём делать",
               "что начинаем делать",
               "что пробуем один спринт и смотрим"], ordered=True)
    s.gap(80)
    s.empty_grid(6, 2, color=GREEN)

    out = b.save("retro.holst")
    print("Готово:", out, "—", len(b.objects), "объектов")


if __name__ == "__main__":
    main()
