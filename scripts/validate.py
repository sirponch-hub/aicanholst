#!/usr/bin/env python3
"""Проверка .holst перед выдачей: схема + вместимость текста.

    python scripts/validate.py board.holst

Что ловит:
  • отсутствующие обязательные поля объектов;
  • архив собран со сжатием (Холст ждёт ZIP_STORED);
  • bounds не соответствует width * textScale;
  • текст не влезает в свою фигуру или стикер;
  • объект уходит ниже границы кадра;
  • кегль мельче 2% высоты кадра (нечитаемо).

Выход: 0 — чисто, 1 — есть ошибки.
"""

from __future__ import annotations

import json
import math
import sys
import zipfile

GLYPH_W, LINE_H = 0.565, 1.28
REQUIRED = ("id", "type", "position", "bounds", "zIndex", "created", "parentId")
MIN_FS_RATIO = 0.02          # 2% высоты кадра
TEXT_TYPES = ("sticker", "simple-text", "shape")


def lines_of(obj):
    state = obj.get("jsonState")
    if not state:
        return []
    return ["".join(leaf.get("text", "") for leaf in child["children"])
            for node in json.loads(state["children"]) for child in node["children"]]


def font_size(obj):
    if obj["type"] == "simple-text":
        return 14 * obj.get("textScale", 1)
    if obj["type"] == "sticker":
        return 14 * obj.get("textScale", 1)     # Холст сам подгоняет, оценка сверху
    return obj.get("fontSize", 30)


def need_height(obj):
    """Фактическая высота текста объекта в пикселях."""
    lines = lines_of(obj)
    if not any(lines):
        return 0
    fs = font_size(obj)
    width = obj["bounds"]["width"] - (fs * 0.6 if obj["type"] == "shape" else 0)
    per = max(1, int(width / (GLYPH_W * fs)))
    return sum(max(1, math.ceil(len(l) / per)) for l in lines) * fs * LINE_H


def check(path):
    errors, warnings = [], []

    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.compress_type != zipfile.ZIP_STORED:
                errors.append("Архив сжат (%s) — нужен ZIP_STORED" % info.filename)
                break
        data = json.loads(z.read("data.json"))
        assets = {i.filename for i in z.infolist()} - {"data.json"}

    objects = data.get("objects", [])
    if not objects:
        errors.append("В доске нет объектов")

    frames = {o["id"]: o for o in objects if o["type"] == "frame"}
    ids = {o["id"] for o in objects}

    # --- 1. схема
    prev_z = None
    for o in objects:
        missing = [f for f in REQUIRED if f not in o]
        if missing:
            errors.append("%s: нет полей %s" % (o.get("type", "?"), ", ".join(missing)))
            continue
        if o["parentId"] and o["parentId"] not in ids:
            errors.append("%s: parentId ссылается в никуда" % o["type"])
        if o["type"] in ("sticker", "simple-text"):
            expect = o["width"] * o["textScale"]
            if abs(o["bounds"]["width"] - expect) > 1:
                errors.append("%s: bounds.width %.0f != width*textScale %.0f"
                              % (o["type"], o["bounds"]["width"], expect))
        if o["type"] == "image" and o["name"] not in assets:
            errors.append("image: файл %s отсутствует в архиве" % o["name"])
        if prev_z is not None and o["zIndex"] <= prev_z and not o.get("ignoreZIndex"):
            warnings.append("zIndex не растёт у %s" % o["type"])
        prev_z = o["zIndex"]

    # --- 2. текст и вместимость
    for o in objects:
        if o["type"] not in TEXT_TYPES:
            continue
        need = need_height(o)
        if need and o["type"] in ("shape", "sticker") and need > o["bounds"]["height"] * 0.96:
            errors.append("НЕ ВЛЕЗАЕТ [%s]: %s" % (where(o, frames), preview(o)))

        frame = frames.get(o["parentId"])
        if not frame:
            continue
        height = need if o["type"] == "simple-text" else max(o["bounds"]["height"], need)
        bottom = frame["bounds"]["y"] + frame["bounds"]["height"]
        if o["bounds"]["y"] + height > bottom - 20:
            errors.append("НИЖЕ КАДРА [%s]: %s" % (frame["labelText"], preview(o)))
        if o["bounds"]["x"] + o["bounds"]["width"] > frame["bounds"]["x"] + frame["bounds"]["width"]:
            errors.append("ШИРЕ КАДРА [%s]: %s" % (frame["labelText"], preview(o)))
        if any(lines_of(o)) and font_size(o) < frame["bounds"]["height"] * MIN_FS_RATIO:
            warnings.append("МЕЛКИЙ КЕГЛЬ %.0f [%s]: %s"
                            % (font_size(o), frame["labelText"], preview(o)))

    return errors, warnings, len(objects), len(frames)


def where(obj, frames):
    frame = frames.get(obj["parentId"])
    return frame["labelText"] if frame else "вне кадра"


def preview(obj, n=40):
    lines = [l for l in lines_of(obj) if l]
    return (lines[0][:n] + "…") if lines else "(пусто)"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    errors, warnings, n_obj, n_frames = check(sys.argv[1])

    for w in warnings:
        print("⚠  " + w)
    for e in errors:
        print("✗  " + e)

    print("\n%d объектов, %d кадров — %s"
          % (n_obj, n_frames, "ОК" if not errors else "%d ошибок" % len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
