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

from holst import (Board, SHAPES_BASIC, STAMP_KEYS, object_text,  # noqa: E402
                   text_height, BLUE, GRAY3, GREEN, VIOLET10, WHITE1, YELLOW)

COL = 800.0          # шаг сетки стенда
ROW = 900.0
LABEL_SCALE = 4.0
LABEL_GAP = 30.0     # воздух между подписью и объектом


def main():
    b = Board("Стенд элементов")
    x0, y0 = 0.0, 0.0

    def label(col, row, text):
        """Подпись над ячейкой сетки. Высота считается по тексту, а не берётся
        на глаз: двухстрочная подпись иначе наезжает на свой же объект."""
        w = COL - 40
        h = text_height(text, w, LABEL_SCALE)
        b.text(x0 + col * COL, y0 + row * ROW - h - LABEL_GAP, text,
               scale=LABEL_SCALE, width_units=w, markdown=False)

    def at(col, row):
        return x0 + col * COL, y0 + row * ROW

    # ── ряд 0: базовые ────────────────────────────────────────────────────
    label(0, 0, "sticker")
    b.sticker(*at(0, 0), "стикер", color=YELLOW, scale=1.5)

    label(1, 0, "sticker-stack")
    b.sticker_stack(*at(1, 0))

    label(2, 0, "simple-text с разметкой")
    b.text(*at(2, 0), "**Жирный**, *курсив*, {red10|цветной}",
           scale=5.0, width_units=COL - 60)

    label(3, 0, "shape + текст")
    b.shape(*at(3, 0), 400, 260, "фигура", fill=BLUE, font_size=60)

    label(4, 0, "flip-card")
    b.flip_card(*at(4, 0), "лицо", "оборот", scale=1.0)

    # ── ряд 1: формы (широкий блок на всю строку) ─────────────────────────
    label(0, 1, "shape: 19 базовых форм, плюс наборы flowchart и bpmn")
    for i, kind in enumerate(SHAPES_BASIC):
        b.shape(x0 + (i % 10) * 200, y0 + ROW + (i // 10) * 200, 170, 170,
                shape_type=kind, fill=WHITE1)

    # ── ряд 2: документы и задачи ────────────────────────────────────────
    label(0, 2, "card — документ с заголовками")
    b.card(*at(0, 2), "# Заголовок\nОбычный абзац с **выделением**.\n"
                      "## Подзаголовок\nЕщё текст.\n### Третий уровень\nИ ещё.",
           height=520)

    label(1, 2, "task-card сама по себе")
    b.task_card(*at(1, 2), "отдельная задача")

    # Канбан шире колонки — занимает оставшуюся часть строки, подписей справа нет.
    label(2, 2, "kanban: карточки связаны через columnId")
    kx, ky = at(2, 2)
    kb = b.kanban(kx, ky, ["Нужно сделать", "В работе", "Готово"])
    for i, title in enumerate(["собрать доску", "проверить импорт", "починить"]):
        b.task_card(kx + i * 374, ky + 120, title, kanban=kb, column=i)

    # ── ряд 3: таблица, mind-map, код, ссылка ────────────────────────────
    label(0, 3, "table 3×3")
    b.table(*at(0, 3), [["метрика", "было", "стало"],
                        ["время сборки", "1 ч", "5 мин"],
                        ["ошибок вёрстки", "12", "0"]],
            col_w=220.0)

    label(1, 3, "mind-map-node + arrow")
    mx, my = at(1, 3)
    root = b.mind_map_node(mx, my, "корень")
    for i, name in enumerate(["ветка 1", "ветка 2"]):
        node = b.mind_map_node(mx + 320, my + i * 140, name, color=VIOLET10)
        b.arrow_between(root, node, width=3)

    label(2, 3, "code")
    b.code(*at(2, 3), "def hello():\n    return 'Холст'")

    label(3, 3, "link")
    b.link(*at(3, 3), "https://holst.so", "Холст",
           "Онлайн-доска для команд", scale=1.0)

    label(4, 3, "dice")
    b.dice(*at(4, 3), faces=6, value=4)

    # ── ряд 4: интерактив и мелочи ───────────────────────────────────────
    label(0, 4, "spinner-wheel")
    b.spinner(*at(0, 4), ["Вариант 1", "Вариант 2", "Вариант 3"], scale=0.8)

    label(1, 4, "phosphor-icon")
    ix, iy = at(1, 4)
    for i, name in enumerate(["check-circle", "warning", "lightbulb", "rocket"]):
        b.icon(ix + i * 70, iy, name, size=48)

    label(2, 4, "reaction-stamp — все ключи")
    sx, sy = at(2, 4)
    for i, key in enumerate(STAMP_KEYS):
        b.stamp(sx + (i % 4) * 70, sy + (i // 4) * 70, key)

    label(3, 4, "штамп, прилипший к стикеру")
    tx, ty = at(3, 4)
    target = b.sticker(tx, ty, "оценка", color=GRAY3)
    b.stamp(tx + 120, ty + 120, "heart", on=target, at=(0.75, 0.75))

    label(4, 4, "drawing")
    # Путь только вниз от точки привязки: с отрицательным y рисунок полез бы
    # вверх, на собственную подпись.
    dx, dy = at(4, 4)
    b.drawing(dx, dy, [(0, 40), (60, 0), (120, 120), (180, 20), (240, 90)],
              stroke_width=6)

    # ── ряд 5: группа и кадр ─────────────────────────────────────────────
    label(0, 5, "group из трёх стикеров")
    gx, gy = at(0, 5)
    b.group([b.sticker(gx + i * 210, gy, str(i + 1), color=GREEN)
             for i in range(3)])

    label(1, 5, "frame с содержимым")
    fx, fy = at(1, 5)
    f = b.frame(fx, fy, 900, 500, "Кадр внутри стенда")
    b.text(fx + 60, fy + 60, "текст в кадре", scale=5.0, width_units=700,
           parent=f)

    check_overlaps(b)
    out = b.save("elements-test.holst")
    types = sorted({o["type"] for o in b.objects})
    print("Готово: %s — %d объектов, %d типов" % (out, len(b.objects), len(types)))
    print("Типы:", ", ".join(types))


def check_overlaps(b):
    """Стенд должен читаться: ни один объект не наезжает на подпись.

    Проверять это глазами бесполезно — доска большая. Считаем пересечения
    прямоугольников; дети фреймов, таблиц и групп не в счёт.
    """
    def box(o):
        d = o["bounds"]
        return d["x"], d["y"], d["x"] + d["width"], d["y"] + d["height"]

    labels = [o for o in b.objects if o["type"] == "simple-text"
              and not o.get("parentId")]
    # group и arrow — рамки вокруг чужих объектов, а не самостоятельные блоки.
    solid = [o for o in b.objects
             if o["type"] not in ("simple-text", "group", "arrow")
             and not o.get("parentId")]

    hits = []
    for lab in labels:
        ax1, ay1, ax2, ay2 = box(lab)
        for o in solid:
            bx1, by1, bx2, by2 = box(o)
            if min(ax2, bx2) - max(ax1, bx1) > 2 and min(ay2, by2) - max(ay1, by1) > 2:
                hits.append((lab, o))
    if hits:
        for lab, o in hits:
            print("НАЛОЖЕНИЕ: подпись «%s» ← %s"
                  % (object_text(lab)[:40], o["type"]))
        raise SystemExit("стенд нечитаем: %d наложений" % len(hits))


if __name__ == "__main__":
    main()
