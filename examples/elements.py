#!/usr/bin/env python3
"""Стенд всех типов объектов — для проверки обратным импортом.

Собирает доску, где каждый элемент подписан. Загрузите её в Холст через
«восстановить доску из файла» и посмотрите, что открылось: это единственный
способ убедиться, что библиотека пишет объекты правильно.

    python3 examples/elements.py
    python3 scripts/validate.py elements-test.holst
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from holst import (Board, SHAPES_BASIC, STAMP_KEYS,     # noqa: E402
                   BLUE, GRAY3, GREEN, RED10, VIOLET10, WHITE1, YELLOW)

COL = 700.0          # шаг сетки стенда
ROW = 900.0


def main():
    b = Board("Стенд элементов")
    x0, y0 = 0.0, 0.0

    def label(col, row, text, dy=-90):
        b.text(x0 + col * COL, y0 + row * ROW + dy, text, scale=4.0,
               width_units=COL - 40)

    # ── ряд 0: базовые ────────────────────────────────────────────────────
    label(0, 0, "sticker")
    b.sticker(x0, y0, "стикер", color=YELLOW, scale=1.5)

    label(1, 0, "sticker-stack")
    b.sticker_stack(x0 + COL, y0)

    label(2, 0, "simple-text")
    b.text(x0 + 2 * COL, y0, "**Жирный**, *курсив*, {red10|цветной}",
           scale=5.0, width_units=COL - 60)

    label(3, 0, "shape + текст")
    b.shape(x0 + 3 * COL, y0, 400, 260, "фигура", fill=BLUE, font_size=60)

    label(4, 0, "flip-card")
    b.flip_card(x0 + 4 * COL, y0, "лицо", "оборот", scale=1.0)

    # ── ряд 1: формы ──────────────────────────────────────────────────────
    label(0, 1, "shape: 19 базовых форм + flowchart-* и bpmn-*")
    for i, kind in enumerate(SHAPES_BASIC):
        b.shape(x0 + (i % 10) * 200, y0 + ROW + (i // 10) * 220, 170, 170,
                shape_type=kind, fill=WHITE1)

    # ── ряд 2: карточки и задачи ──────────────────────────────────────────
    label(0, 2, "card — документ с заголовками")
    b.card(x0, y0 + 2 * ROW,
           "# Заголовок\nОбычный абзац с **выделением**.\n"
           "## Подзаголовок\nЕщё текст.\n### Третий уровень\nИ ещё.",
           height=520)

    label(1, 2, "task-card (сама по себе)")
    b.task_card(x0 + COL, y0 + 2 * ROW, "отдельная задача")

    label(2, 2, "kanban + task-card в колонках")
    kb = b.kanban(x0 + 2 * COL, y0 + 2 * ROW, ["Нужно сделать", "В работе", "Готово"])
    for i, title in enumerate(["собрать доску", "проверить импорт", "починить"]):
        b.task_card(x0 + 2 * COL + i * 374, y0 + 2 * ROW + 120, title,
                    kanban=kb, column=i)

    # ── ряд 3: таблица, mind-map, код ─────────────────────────────────────
    label(0, 3, "table 3×3")
    b.table(x0, y0 + 3 * ROW,
            [["метрика", "было", "стало"],
             ["время сборки", "1 ч", "5 мин"],
             ["ошибок вёрстки", "12", "0"]])

    label(1, 3, "mind-map-node + arrow")
    root = b.mind_map_node(x0 + COL, y0 + 3 * ROW, "корень", width=200)
    for i, name in enumerate(["ветка 1", "ветка 2"]):
        node = b.mind_map_node(x0 + COL + 400, y0 + 3 * ROW + i * 140, name,
                               width=200, color=VIOLET10)
        b.arrow_between(root, node, width=3)

    label(2, 3, "code")
    b.code(x0 + 2 * COL, y0 + 3 * ROW, "def hello():\n    return 'Холст'")

    label(3, 3, "link")
    b.link(x0 + 3 * COL, y0 + 3 * ROW, "https://holst.so",
           "Холст", "Онлайн-доска для совместной работы", scale=1.0)

    # ── ряд 4: интерактив и мелочи ────────────────────────────────────────
    label(0, 4, "dice")
    b.dice(x0, y0 + 4 * ROW, faces=6, value=4)

    label(1, 4, "spinner-wheel")
    b.spinner(x0 + COL, y0 + 4 * ROW, ["Вариант 1", "Вариант 2", "Вариант 3"],
              scale=0.8)

    label(2, 4, "phosphor-icon")
    for i, name in enumerate(["check-circle", "warning", "lightbulb", "rocket"]):
        b.icon(x0 + 2 * COL + i * 70, y0 + 4 * ROW, name, size=48)

    label(3, 4, "reaction-stamp — все ключи")
    for i, key in enumerate(STAMP_KEYS):
        b.stamp(x0 + 3 * COL + i * 70, y0 + 4 * ROW, key)

    label(4, 4, "штамп, прилипший к стикеру")
    target = b.sticker(x0 + 4 * COL, y0 + 4 * ROW, "оценка", color=GRAY3)
    b.stamp(x0 + 4 * COL + 120, y0 + 4 * ROW + 120, "heart", on=target,
            at=(0.75, 0.75))

    # ── ряд 5: рисунок и группа ───────────────────────────────────────────
    label(0, 5, "drawing")
    b.drawing(x0, y0 + 5 * ROW,
              [(0, 0), (60, -80), (120, 40), (180, -60), (240, 0)],
              stroke_width=6)

    label(1, 5, "group из трёх стикеров")
    trio = [b.sticker(x0 + COL + i * 210, y0 + 5 * ROW, str(i + 1),
                      color=GREEN) for i in range(3)]
    b.group(trio)

    label(2, 5, "frame с содержимым")
    f = b.frame(x0 + 2 * COL, y0 + 5 * ROW, 900, 500, "Кадр внутри стенда")
    b.text(x0 + 2 * COL + 60, y0 + 5 * ROW + 60, "текст в кадре", scale=5.0,
           width_units=700, parent=f)

    out = b.save("elements-test.holst")
    types = sorted({o["type"] for o in b.objects})
    print("Готово: %s — %d объектов, %d типов" % (out, len(b.objects), len(types)))
    print("Типы:", ", ".join(types))


if __name__ == "__main__":
    main()
