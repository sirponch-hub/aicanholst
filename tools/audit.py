#!/usr/bin/env python3
"""Сверка библиотеки с эталонной выгрузкой из Холста.

    python3 tools/audit.py input/elements.holst

Для каждого типа объекта из эталона строит такой же объект библиотекой и
сравнивает наборы полей. Показывает три вещи:

  ✗ ТИПА НЕТ      — библиотека не умеет такой объект вовсе;
  − нет полей     — Холст пишет, а мы нет (объект может повести себя странно);
  + лишние поля   — мы пишем, а Холст нет (обычно безвредно, но подозрительно).

Эталон — доска, на которую вручную вынесены все элементы Холста.
"""

from __future__ import annotations

import json
import os
import sys
import zipfile
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import holst  # noqa: E402
from holst import Board  # noqa: E402

COMMON = {"id", "type", "position", "bounds", "zIndex", "created", "updated", "parentId"}

# Поля, которых у нас нет и не должно быть: они появляются только у объектов,
# которые библиотека не создаёт (аудио- и видеофайлы).
OPTIONAL = {"file": {"audioInfo", "videoInfo"}}


def norm(field):
    """column-1, row-7 → column-N, row-N: сравниваем форму, а не размер таблицы."""
    for prefix in ("column-", "row-", "merge-"):
        if field.startswith(prefix) and field[len(prefix):].replace("-", "").isdigit():
            return prefix + "N"
    return field

# Как построить каждый тип нашей библиотекой. None — не умеем.
IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_probe.png")


def builders(b):
    """type -> вызов, создающий объект этого типа."""
    return {
        "frame": lambda: b.frame(0, 0, 1920, 1080, "Фрейм 1"),
        "sticker": lambda: b.sticker(0, 0, "текст"),
        "simple-text": lambda: b.text(0, 0, "текст"),
        "shape": lambda: b.shape(0, 0, 100, 100, "текст"),
        "image": lambda: b.image(0, 0, IMG, 380, 380),
        "file": lambda: b.file(0, 0, IMG, pages=101),
        "link": lambda: b.link(0, 0, "https://example.com", "t", "d"),
        "arrow": lambda: b.arrow(0, 0, 100, 100),
        "drawing": lambda: b.drawing(0, 0, [(0, 0), (10, 10)]),
        "group": lambda: b.group([b.sticker(0, 0)]),
        "flip-card": lambda: b.flip_card(0, 0, "a", "b"),
        # Собираем самый богатый вариант: у прилипшего штампа есть
        # stickyPosition, у канбанной карточки — columnId/swimlaneId.
        "reaction-stamp": lambda: b.stamp(0, 0, on=b.sticker(0, 0)),
        "card": lambda: b.card(0, 0, "заголовок"),
        "task-card": lambda: b.task_card(
            0, 0, "task", kanban=b.kanban(0, 0, ["Нужно сделать"])),
        "kanban": lambda: b.kanban(0, 0, ["Нужно сделать", "В работе"]),
        "mind-map-node": lambda: b.mind_map_node(0, 0, "1"),
        "code": lambda: b.code(0, 0, "print(1)"),
        "dice": lambda: b.dice(0, 0),
        "spinner-wheel": lambda: b.spinner(0, 0, ["Вариант 1", "Вариант 2"]),
        "sticker-stack": lambda: b.sticker_stack(0, 0),
        "phosphor-icon": lambda: b.icon(0, 0, "align-right-simple"),
        "table": lambda: b.table(0, 0, [["a", "b"], ["c", "d"]]),
        "table-cell": lambda: [o for o in b.objects
                               if o["type"] == "table-cell"][-1],
    }


def main():
    ref_path = sys.argv[1] if len(sys.argv) > 1 else "input/elements.holst"
    with zipfile.ZipFile(ref_path) as z:
        ref = json.loads(z.read("data.json"))

    # Поля, которые Холст реально пишет для каждого типа (объединение по всем
    # объектам этого типа — разные экземпляры несут разные необязательные поля).
    ref_fields, counts = {}, Counter()
    for o in ref["objects"]:
        fields = {norm(f) for f in set(o) - COMMON}
        ref_fields.setdefault(o["type"], set()).update(fields)
        counts[o["type"]] += 1
    for t, opt in OPTIONAL.items():
        if t in ref_fields:
            ref_fields[t] -= opt

    if not os.path.exists(IMG):
        with open(IMG, "wb") as fh:                  # 1x1 PNG для проб
            fh.write(bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
                "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
                "00000049454e44ae426082"))

    b = Board("audit")
    made = builders(b)

    missing_types, diffs, ok = [], [], []
    for t in sorted(ref_fields):
        build = made.get(t, "unknown")
        if build is None or build == "unknown":
            missing_types.append((t, counts[t], build == "unknown"))
            continue
        try:
            obj = build()
        except Exception as exc:                      # noqa: BLE001
            missing_types.append((t, counts[t], False))
            diffs.append((t, set(), set(), "ошибка сборки: %s" % exc))
            continue
        ours = {norm(f) for f in set(obj) - COMMON}
        lack, extra = ref_fields[t] - ours, ours - ref_fields[t]
        (diffs if lack else ok).append((t, lack, extra, ""))

    print("ЭТАЛОН: %s — %d объектов, %d типов\n" % (
        os.path.basename(ref_path), len(ref["objects"]), len(ref_fields)))

    if missing_types:
        print("НЕ УМЕЕМ СОЗДАВАТЬ:")
        for t, n, unknown in missing_types:
            print("  ✗ %-18s (%d шт.)%s" % (t, n, "" if unknown else "  — вручную"))
        print()

    if diffs:
        print("НЕ ХВАТАЕТ ПОЛЕЙ (Холст их пишет, мы нет):")
        for t, lack, extra, err in diffs:
            print("  %s" % t)
            if err:
                print("      %s" % err)
            if lack:
                print("      − %s" % ", ".join(sorted(lack)))
        print()

    extras = [(t, e) for t, _, e, _ in ok + diffs if e]
    if extras:
        print("ПИШЕМ БОЛЬШЕ ЭТАЛОНА (необязательные поля, Холст их принимает):")
        for t, e in sorted(extras):
            print("  %-16s %s" % (t, ", ".join(sorted(e))))
        print()

    if ok:
        print("ПОКРЫТЫ: %s" % ", ".join(t for t, *_ in ok))

    total = len(ref_fields)
    print("\nИтог: %d из %d типов покрыты, %d неполных, %d не умеем." % (
        len(ok), total, len(diffs), len(missing_types)))
    return 1 if (missing_types or diffs) else 0


if __name__ == "__main__":
    sys.exit(main())
