#!/usr/bin/env python3
"""Рендер кадров .holst в PNG — чтобы посмотреть композицию глазами.

    python scripts/preview.py board.holst out/            # все кадры
    python scripts/preview.py board.holst out/ 0 3 7      # только кадры 0, 3, 7

Нужен cairosvg: pip install cairosvg
Без него скрипт всё равно положит рядом .svg — их можно открыть браузером.

Важно: самодельный рендер не переносит строки внутри фигур и не центрирует
текст так, как это делает Холст. Текст может торчать за край, хотя в Холсте
всё в порядке. Смотри на композицию, а вместимость проверяй validate.py.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from holst import FS_INTERNAL, LINE_H, ems  # noqa: E402

ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def wrap(text, width, fs):
    """Перенос строк той же метрикой Inter, что использует сборка."""
    if width <= 0:
        return [text]
    out = []
    for para in str(text).split("\n"):
        cur = ""
        for i, word in enumerate(para.split(" ")):
            candidate = (cur + " " + word) if cur else word
            if cur and ems(candidate) * fs > width:
                out.append(cur)
                cur = word
            else:
                cur = candidate
        out.append(cur)
    return out


def esc(s):
    return "".join(ESC.get(c, c) for c in str(s))


def hexc(value, default="#cccccc"):
    if isinstance(value, dict):
        value = value.get("color")
    return default if value is None else "#%06x" % value


def lines_of(obj):
    state = obj.get("jsonState")
    if not state:
        return []
    return ["".join(leaf.get("text", "") for leaf in child["children"])
            for node in json.loads(state["children"]) for child in node["children"]]


def render_frame(frame, objects, assets):
    fb = frame["bounds"]
    ox, oy = fb["x"], fb["y"]
    out = ['<svg xmlns="http://www.w3.org/2000/svg" '
           'xmlns:xlink="http://www.w3.org/1999/xlink" '
           'viewBox="0 0 %d %d" width="%d" height="%d">'
           % (fb["width"], fb["height"], fb["width"], fb["height"]),
           '<rect width="100%%" height="100%%" fill="%s"/>' % hexc(frame.get("fillColor"), "#ffffff")]

    for o in sorted(objects, key=lambda o: o.get("zIndex", 0)):
        if o["parentId"] != frame["id"] or o["type"] == "frame":
            continue
        b = o["bounds"]
        x, y, w, h = b["x"] - ox, b["y"] - oy, b["width"], b["height"]
        t = o["type"]

        if t == "sticker":
            out.append('<rect x="%f" y="%f" width="%f" height="%f" fill="%s" rx="8"/>'
                       % (x, y, w, h, hexc(o.get("fillColor"), "#fff9b1")))
        elif t == "shape":
            fill, stroke = hexc(o.get("fillColor"), "#ffffff"), hexc(o.get("strokeColor"), "#808080")
            if o.get("shapeType") == "ellipse":
                out.append('<ellipse cx="%f" cy="%f" rx="%f" ry="%f" fill="%s" stroke="%s" stroke-width="3"/>'
                           % (x + w / 2, y + h / 2, w / 2, h / 2, fill, stroke))
            else:
                out.append('<rect x="%f" y="%f" width="%f" height="%f" fill="%s" stroke="%s" stroke-width="3"/>'
                           % (x, y, w, h, fill, stroke))
        elif t == "arrow":
            s, e = o["start"]["point"], o["end"]["point"]
            out.append('<line x1="%f" y1="%f" x2="%f" y2="%f" stroke="%s" stroke-width="%s"/>'
                       % (s["x"] - ox, s["y"] - oy, e["x"] - ox, e["y"] - oy,
                          hexc(o.get("strokeColor"), "#1a1a1a"), o.get("strokeWidth", 5)))
        elif t == "image" and o["name"] in assets:
            ext = os.path.splitext(o["name"])[1].lstrip(".") or "png"
            b64 = base64.b64encode(assets[o["name"]]).decode()
            out.append('<image x="%f" y="%f" width="%f" height="%f" xlink:href="data:image/%s;base64,%s"/>'
                       % (x, y, w, h, ext, b64))

        raw = [l for l in lines_of(o) if l]
        if raw:
            fs = (FS_INTERNAL * o["textScale"] if t in ("simple-text", "sticker")
                  else o.get("fontSize", 30))
            # Переносим так же, как считает сборка — переполнение видно сразу.
            box = w - (fs * 0.6 if t == "shape" else 0)
            lines = wrap("\n".join(raw), box, fs) if t != "sticker" else raw
            anchor = {"center": "middle", "right": "end"}.get(
                o.get("horizontalAlign"), "start")
            tx = x + (w / 2 if anchor == "middle" else (w if anchor == "end" else 0))
            ty = y + fs
            if t in ("shape", "sticker"):
                ty = y + h / 2 - (len(lines) - 1) * fs * LINE_H / 2 + fs * 0.35
            color = hexc(o.get("textColor"), "#1a1a1a")
            for i, line in enumerate(lines):
                out.append('<text x="%f" y="%f" font-family="Inter, sans-serif" '
                           'font-size="%f" fill="%s" text-anchor="%s">%s</text>'
                           % (tx, ty + i * fs * LINE_H, fs, color, anchor, esc(line)))

    out.append("</svg>")
    return "\n".join(out)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    want = {int(a) for a in sys.argv[3:]}
    os.makedirs(dst, exist_ok=True)

    with zipfile.ZipFile(src) as z:
        data = json.loads(z.read("data.json"))
        assets = {i.filename: z.read(i.filename) for i in z.infolist()
                  if i.filename != "data.json"}

    frames = [o for o in data["objects"] if o["type"] == "frame"]
    try:
        import cairosvg
    except ImportError:
        cairosvg = None
        print("cairosvg не найден — сохраняю только .svg (pip install cairosvg)")

    for i, frame in enumerate(frames):
        if want and i not in want:
            continue
        name = "%02d_%s" % (i, "".join(c if c.isalnum() else "_"
                                       for c in frame.get("labelText", "frame"))[:40])
        svg_path = os.path.join(dst, name + ".svg")
        with open(svg_path, "w", encoding="utf-8") as fh:
            fh.write(render_frame(frame, data["objects"], assets))
        if cairosvg:
            cairosvg.svg2png(url=svg_path, write_to=os.path.join(dst, name + ".png"),
                             output_width=1800)
            try:
                os.remove(svg_path)
            except OSError:
                pass
        print("→", name)

    print("\n%d кадров всего, отрендерено в %s" % (len(frames), dst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
