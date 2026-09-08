#!/usr/bin/env python3
"""Рендер кадров .holst в PNG — чтобы посмотреть композицию глазами.

    python scripts/preview.py board.holst out/            # все кадры
    python scripts/preview.py board.holst out/ 0 3 7      # только кадры 0, 3, 7
    python scripts/preview.py board.holst out/ --all      # доска целиком

Без кадров (или с --all) рисуется вся доска одной картинкой: объекты, которые
лежат вне фреймов, иначе не видно вовсе. Типы, которые рендерер не рисует
всерьёз — карточки, канбан, таблица, кость, колесо, иконки, штампы, — идут
пунктирными габаритами с подписью типа: для проверки композиции этого хватает.

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


# Приближение палитры Холста для превью: точных значений мы не знаем,
# важно лишь отличать светлое от тёмного и цвет от серого.
TOKENS = {
    "white1": "#ffffff", "white3": "#fcfcfc", "white6": "#f2f2f2",
    "gray3": "#ededed", "gray7": "#c7c7c7", "gray8": "#b0b0b0",
    "gray10": "#8f8f8f", "gray12": "#1a1a1a",
    "yellow4": "#fff3c4", "pink10": "#d6409f", "red10": "#e5484d",
    "violet10": "#6e56cf",
}


def hexc(value, default="#cccccc"):
    if isinstance(value, dict):
        value = value.get("color")
    if value is None:
        return default
    if isinstance(value, str):
        # Токен палитры: white1, gray12, violet10… Неизвестный — по шкале имени.
        if value in TOKENS:
            return TOKENS[value]
        step = "".join(c for c in value if c.isdigit())
        if value.startswith(("white", "gray")) and step:
            v = max(0, min(255, int(255 - int(step) * 20)))
            return "#%02x%02x%02x" % (v, v, v)
        return default
    return "#%06x" % value


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
        if o["parentId"] != frame["id"] or o is frame:
            continue
        if o["type"] == "frame":       # вложенный кадр — рамкой с подписью
            fb2 = o["bounds"]
            out.append('<rect x="%f" y="%f" width="%f" height="%f" fill="%s" '
                       'stroke="#8f8f8f" stroke-width="3"/>'
                       % (fb2["x"] - ox, fb2["y"] - oy, fb2["width"], fb2["height"],
                          hexc(o.get("fillColor"), "#ffffff")))
            out.append('<text x="%f" y="%f" font-family="Inter, sans-serif" '
                       'font-size="26" fill="#8f8f8f">%s</text>'
                       % (fb2["x"] - ox, fb2["y"] - oy - 8,
                          esc(o.get("labelText", ""))))
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
        elif t == "drawing" and o.get("path"):
            nums = [float(v) for v in o["path"].split(",")]
            px, py = o["position"]["x"] - ox, o["position"]["y"] - oy
            pts = " ".join("%f,%f" % (px + nums[i], py + nums[i + 1])
                           for i in range(0, len(nums) - 1, 2))
            out.append('<polyline points="%s" fill="none" stroke="%s" '
                       'stroke-width="%s" stroke-linecap="round"/>'
                       % (pts, hexc(o.get("color"), "#1a1a1a"),
                          o.get("strokeWidth", 6)))
        elif t not in ("simple-text", "group"):
            # Остальные типы (карточки, канбан, таблица, кость, колесо, иконки,
            # штампы) рисуем габаритами с подписью типа: для композиции этого
            # достаточно, а рисовать каждый всерьёз — отдельный проект.
            out.append('<rect x="%f" y="%f" width="%f" height="%f" fill="%s" '
                       'stroke="#b0b0b0" stroke-width="2" stroke-dasharray="8 6" rx="6"/>'
                       % (x, y, w, h, hexc(o.get("fillColor"), "#fbfbfb")))
            out.append('<text x="%f" y="%f" font-family="Inter, sans-serif" '
                       'font-size="%f" fill="#8f8f8f">%s</text>'
                       % (x + 6, y + min(28, h - 4), min(24, max(9, h / 4)), esc(t)))

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
    want = {int(a) for a in sys.argv[3:] if a.isdigit()}
    os.makedirs(dst, exist_ok=True)

    with zipfile.ZipFile(src) as z:
        data = json.loads(z.read("data.json"))
        assets = {i.filename: z.read(i.filename) for i in z.infolist()
                  if i.filename != "data.json"}

    frames = [o for o in data["objects"] if o["type"] == "frame"]
    if not frames or "--all" in sys.argv:
        # Доска без кадров (или явный --all): рисуем всё целиком, подставив
        # виртуальный кадр по габаритам объектов.
        xs = [o["bounds"]["x"] for o in data["objects"]]
        ys = [o["bounds"]["y"] for o in data["objects"]]
        x2 = [o["bounds"]["x"] + o["bounds"]["width"] for o in data["objects"]]
        y2 = [o["bounds"]["y"] + o["bounds"]["height"] for o in data["objects"]]
        pad = 80
        virtual = {
            "id": None, "type": "frame", "labelText": "вся доска",
            "fillColor": {"color": 0xFFFFFF},
            "bounds": {"x": min(xs) - pad, "y": min(ys) - pad,
                       "width": max(x2) - min(xs) + 2 * pad,
                       "height": max(y2) - min(ys) + 2 * pad},
        }
        # Дети групп рисуем как верхнеуровневые: группа — это рамка вокруг
        # чужих объектов, а не контейнер со своим фоном.
        groups = {o["id"] for o in data["objects"] if o["type"] == "group"}
        for o in data["objects"]:
            if o.get("parentId") in groups:
                o["parentId"] = None
        frames = [virtual]
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
