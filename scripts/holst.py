"""holst.py — генератор .holst файлов (доски Холст / holst.ru).

Формат разобран реверс-инжинирингом и подтверждён экспериментально.
Библиотека не связана с ООО «Холст» и не является официальной.

Быстрый старт:

    from holst import Board, YELLOW, fit_scale

    b = Board("Моя доска")
    f = b.slide(0, 0, "Кадр 16:9")
    b.sticker(400, 800, "Привет", color=YELLOW, scale=3, parent=f)
    b.save("board.holst")

Открывается в Холсте через «восстановить доску из файла».
"""

from __future__ import annotations

import json
import math
import os
import time
import uuid
import zipfile

__version__ = "1.0.0"

# Цвета — десятичный int (0xRRGGBB). Холст также принимает строковые токены
# палитры ("yellow4", "gray3"), но int надёжнее.
YELLOW = 0xFFF9B1
GREEN = 0xD5F692
BLUE = 0xA6CCF5
PINK = 0xF5D0E9
ORANGE = 0xFFD599
PURPLE = 0xD0C6F5
RED = 0xFF9D9D
GRAY = 0xD9D9D9
WHITE = 0xFFFFFF
BLACK = 0x1A1A1A
DARK_GRAY = 0x808080

DEFAULT_FONT = "OpenSans"

# ---------------------------------------------------------------- типографика
GLYPH_W, LINE_H = 0.585, 1.28   # ширина глифа кириллицы и интерлиньяж
FS_FLOOR = 60                   # мельче — нечитаемо на кадре 4800x2700


def text_lines(text, width, fs):
    """Сколько строк займёт текст при данной ширине и кегле."""
    per = max(1, int(width / (GLYPH_W * fs)))
    return sum(max(1, math.ceil(len(l) / per)) for l in str(text).split("\n"))


def fit_scale(text, width, budget, start, floor=4.0, step=0.2):
    """Уменьшает scale текста, пока он не уложится в высоту budget.
    Ниже floor не опускается."""
    sc = start
    while sc - step >= floor and text_lines(text, width, sc * 14) * sc * 14 * LINE_H > budget:
        sc -= step
    return round(sc, 4)


def fit_fs(text, w, h, fs, floor=FS_FLOOR, step=4):
    """Уменьшает font_size фигуры, пока текст не уложится в её высоту.
    Ниже floor не опускается: если текст не влезает даже так — режь текст."""
    while fs - step >= floor and text_lines(text, w - fs * 0.6, fs) * fs * LINE_H > h * 0.94:
        fs -= step
    return fs


def grid_size(cols, rows, w, h, gap=24):
    """Сторона квадратного стикера, вписанного в область w x h."""
    return max(60, min((w - gap * (cols - 1)) / cols, (h - gap * (rows - 1)) / rows))


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> int:
    return int(time.time() * 1000)


def _color(c, opacity: float = 1.0):
    return {"color": c, "opacity": opacity}


def _pid(parent):
    if parent is None:
        return None
    return parent["id"] if isinstance(parent, dict) else parent


def _rich(text: str, bold=False, italic=False, color=None, bullets=False):
    """Строит jsonState. Абзацы делятся по \\n."""
    nodes = []
    for line in str(text).split("\n"):
        leaf = {"text": line}
        if bold:
            leaf["bold"] = True
        if italic:
            leaf["italic"] = True
        if color is not None:
            leaf["color"] = color
        node_type = "ul-list-item" if bullets else ("paragraph" if line else "initial")
        nodes.append({
            "type": "wrapper",
            "key": _uid(),
            "children": [{"type": node_type, "key": _uid(), "children": [leaf]}],
        })
    return {"children": json.dumps(nodes, ensure_ascii=False)}


class Board:
    """Доска. Собирает объекты и пишет их в .holst (ZIP без сжатия).

    author_id — идентификатор автора в поле `created.a`. При импорте доска
    переходит к тому, кто её загрузил, поэтому подойдёт любое целое.
    """

    def __init__(self, name: str = "Board", background=0xF5F5F5, author_id: int = 1):
        self.name = name
        self.background = background
        self.author = author_id
        self.objects: list[dict] = []
        self.assets: dict[str, str] = {}   # имя в архиве -> путь на диске
        self._z = 1000.0

    def _next_z(self) -> float:
        self._z += 1000.0
        return self._z

    def _base(self, otype, x, y, w, h, parent=None, z=None) -> dict:
        return {
            "type": otype,
            "id": _uid(),
            "position": {"x": float(x), "y": float(y)},
            "parentId": _pid(parent),
            "zIndex": self._next_z() if z is None else z,
            "created": {"a": self.author, "t": _now()},
            "updated": None,
            "bounds": {"x": float(x), "y": float(y), "width": float(w), "height": float(h), "type": 1},
        }

    def _add(self, obj: dict) -> dict:
        self.objects.append(obj)
        return obj

    # ------------------------------------------------------------ объекты
    def frame(self, x, y, width, height, label="Frame", fill=WHITE, parent=None, locked=False):
        o = self._base("frame", x, y, width, height, parent)
        o.update({"width": float(width), "height": float(height),
                  "labelText": label, "fillColor": _color(fill)})
        if locked:
            o["locked"] = True
        return self._add(o)

    def slide(self, x, y, label="Slide", fill=WHITE, w=4800):
        """Кадр 16:9 — базовая единица доски. Высота считается сама."""
        return self.frame(x, y, w, w * 9 / 16, label, fill=fill)

    def sticker(self, x, y, text="", color=YELLOW, width=192, height=192, scale=1.0,
                halign="center", valign="center", parent=None, bold=False, italic=False,
                text_color=None):
        """Стикер 192x192 (широкий — width=384). Итоговый размер = width*scale.
        Внимание: scale тянет и высоту. Для широкой плашки с текстом бери shape."""
        o = self._base("sticker", x, y, width * scale, height * scale, parent)
        o.update({
            "textScale": float(scale),
            "fillColor": _color(color),
            "width": float(width),
            "height": float(height),
            "horizontalAlign": halign,
            "verticalAlign": valign,
            "reactions": [],
            "jsonState": _rich(text, bold=bold, italic=italic, color=text_color),
        })
        return self._add(o)

    def text(self, x, y, text="", scale=4.0, width=400, color=DARK_GRAY, fill=None,
             halign="left", font=DEFAULT_FONT, fixed_width=False, parent=None,
             bold=False, italic=False, bullets=False, rotation=0):
        """Свободный текст. Кегль ≈ 14 * scale. bounds.height (40*scale) —
        не фактическая высота: реальная = строки * кегль * 1.28."""
        h = 40.0 * scale
        o = self._base("simple-text", x, y, width * scale, h, parent)
        o.update({
            "width": float(width),
            "textScale": float(scale),
            "textBackgroundColor": {"opacity": 1, "color": None},
            "textColor": _color(color),
            "fixedWidth": bool(fixed_width),
            "horizontalAlign": halign,
            "fontFamily": font,
            "rotation": rotation,
            "jsonState": _rich(text, bold=bold, italic=italic, bullets=bullets),
        })
        if fill is not None:
            o["fillColor"] = _color(fill)
        return self._add(o)

    def shape(self, x, y, width, height, text="", shape_type="square", fill=WHITE,
              stroke=DARK_GRAY, stroke_width=2, stroke_opacity=1.0, stroke_style="solid",
              text_color=BLACK, font_size=26, font=DEFAULT_FONT, halign="center",
              valign="center", rotation=0, parent=None, bold=False, autofit=True):
        """shape_type: square | ellipse | basic-star.
        autofit=True ужимает кегль, если текст не влезает в высоту фигуры."""
        fs = fit_fs(text, width, height, font_size) if (autofit and text) else font_size
        o = self._base("shape", x, y, width, height, parent)
        o.update({
            "fillColor": _color(fill),
            "textColor": _color(text_color),
            "textBackgroundColor": {"opacity": 1, "color": None},
            "strokeColor": _color(stroke, stroke_opacity),
            "strokeStyle": stroke_style,
            "strokeWidth": stroke_width,
            "fontFamily": font,
            "shapeType": shape_type,
            "width": float(width),
            "height": float(height),
            "horizontalAlign": halign,
            "verticalAlign": valign,
            "rotation": rotation,
            "fontSize": fs,
            "fixedSize": True,
            "jsonState": _rich(text, bold=bold),
        })
        return self._add(o)

    def image(self, x, y, path, width=None, height=None, parent=None, link_to=None):
        """Кладёт файл в архив под <uuid>.<ext> и создаёт объект image."""
        if not os.path.isfile(path):
            raise FileNotFoundError("Картинки нет на диске: %s" % path)
        ext = os.path.splitext(path)[1].lower() or ".png"
        asset = _uid() + ext
        self.assets[asset] = path
        width, height = width or 800, height or 600
        o = self._base("image", x, y, width, height, parent)
        o.update({
            "width": float(width),
            "height": float(height),
            "name": asset,
            "isLoading": False,
            "rotation": 0,
            "borderRadius": 0,
            "strokeColor": _color(WHITE, 0),
            "strokeStyle": "solid",
            "strokeWidth": 5,
        })
        if link_to:
            o["linkTo"] = link_to
        return self._add(o)

    def image_fit(self, x, y, box_w, box_h, path, parent=None):
        """Картинка, вписанная в область с сохранением пропорций и центрированием.
        Требует Pillow (pip install pillow)."""
        from PIL import Image
        iw, ih = Image.open(path).size
        k = min(box_w / iw, box_h / ih)
        pw, ph = iw * k, ih * k
        return self.image(x + (box_w - pw) / 2, y + (box_h - ph) / 2, path,
                          width=pw, height=ph, parent=parent)

    def file(self, x, y, path, display_name=None, width=2400, height=1350,
             pages=1, scale=4.0, parent=None):
        """PDF/документ на доске (displayType='content' — превью страницы)."""
        if not os.path.isfile(path):
            raise FileNotFoundError("Файла нет на диске: %s" % path)
        ext = os.path.splitext(path)[1].lower()
        asset = _uid() + ext
        self.assets[asset] = path
        o = self._base("file", x, y, width, height, parent)
        o.update({
            "displayFileName": display_name or os.path.basename(path),
            "fileName": asset,
            "fileSize": os.path.getsize(path),
            "fileType": "",
            "scale": scale,
            "rotation": 0,
            "pinnedPage": 1,
            "pagesInfo": {"count": pages, "valid": True},
            "displayType": "content",
        })
        return self._add(o)

    def link(self, x, y, url, title="", description="", width=600, height=264,
             scale=2.0, parent=None):
        o = self._base("link", x, y, width, height, parent)
        o.update({
            "link": url,
            "linkInfo": {"link": url, "title": title, "description": description},
            "scale": scale,
        })
        return self._add(o)

    def stamp(self, x, y, emoji="👍", size=172, parent=None):
        o = self._base("stamp", x, y, size, size, parent)
        o.update({"width": float(size), "height": float(size),
                  "data": {"type": "textStamp", "text": emoji}, "rotation": 0})
        return self._add(o)

    def drawing(self, x, y, points, color=BLACK, stroke_width=12, parent=None):
        """points — [(dx, dy), …] относительно (x, y). Хранится плоской строкой."""
        flat = ",".join(f"{round(px, 1)},{round(py, 1)}" for px, py in points)
        xs = [p[0] for p in points] or [0]
        ys = [p[1] for p in points] or [0]
        pad = stroke_width
        o = self._base("drawing", x + min(xs) - pad, y + min(ys) - pad,
                       max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad, parent)
        o.update({"algorithm": "lazy", "path": flat, "pivot": {"x": 0, "y": 0},
                  "position": {"x": float(x), "y": float(y)},
                  "strokeWidth": stroke_width, "color": color, "alpha": 1})
        return self._add(o)

    def group(self, children, parent=None, locked=False):
        """Объединяет уже созданные объекты: переписывает им parentId."""
        xs = [c["bounds"]["x"] for c in children]
        ys = [c["bounds"]["y"] for c in children]
        x2 = [c["bounds"]["x"] + c["bounds"]["width"] for c in children]
        y2 = [c["bounds"]["y"] + c["bounds"]["height"] for c in children]
        g = self._base("group", min(xs), min(ys), max(x2) - min(xs), max(y2) - min(ys), parent)
        g["ignoreZIndex"] = True
        if locked:
            g["locked"] = True
        for c in children:
            c["parentId"] = g["id"]
        return self._add(g)

    # ------------------------------------------------------------ стрелки
    def arrow(self, x1, y1, x2, y2, color=BLACK, width=5, style="solid",
              arrow_type="straight", head_end="triangle-filled", head_start="none",
              parent=None):
        o = self._base("arrow", min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1), parent)
        o.update({
            "arrowType": arrow_type,          # straight | curved | elbow
            "texts": [],
            "arrowheadStart": head_start,     # none | triangle-filled | arc | miro
            "arrowheadEnd": head_end,
            "start": {"point": {"x": float(x1), "y": float(y1)}},
            "end": {"point": {"x": float(x2), "y": float(y2)}},
            "position": {"x": 0, "y": 0},
            "strokeColor": _color(color),
            "strokeWidth": width,
            "strokeStyle": style,             # solid | dashed | dotted
            "midwayControls": [],
            "elbowMidwayControls": [],
            "textRotated": False,
        })
        return self._add(o)

    def arrow_between(self, a, b, **kw):
        """Стрелка, привязанная к объектам: от правого края a к левому краю b."""
        ab, bb = a["bounds"], b["bounds"]
        p1 = (ab["x"] + ab["width"], ab["y"] + ab["height"] / 2)
        p2 = (bb["x"], bb["y"] + bb["height"] / 2)
        o = self.arrow(p1[0], p1[1], p2[0], p2[1], **kw)
        o["start"] = {"objectId": a["id"], "point": {"x": p1[0], "y": p1[1]},
                      "relativePoint": {"x": 1, "y": 0.5}}
        o["end"] = {"objectId": b["id"], "point": {"x": p2[0], "y": p2[1]},
                    "relativePoint": {"x": 0, "y": 0.5}}
        return o

    # ------------------------------------------------------------ хелперы
    def sticker_grid(self, x, y, texts, cols=4, color=YELLOW, size=192, gap=24,
                     parent=None, scale=1.0):
        out = []
        step = size * scale + gap
        for i, t in enumerate(texts):
            out.append(self.sticker(x + (i % cols) * step, y + (i // cols) * step,
                                    t, color=color, width=size, height=size,
                                    scale=scale, parent=parent))
        return out

    def empty_grid(self, x, y, cols, rows, w, h, color=YELLOW, gap=24, parent=None):
        """Сетка пустых стикеров, вписанная в область w x h и центрированная в ней."""
        size = grid_size(cols, rows, w, h, gap)
        x0 = x + (w - (cols * size + (cols - 1) * gap)) / 2
        for r in range(rows):
            for c in range(cols):
                self.sticker(x0 + c * (size + gap), y + r * (size + gap), "",
                             color=color, scale=size / 192.0, parent=parent)

    # ------------------------------------------------------------ запись
    def to_json(self) -> dict:
        return {
            "boardName": self.name,
            "version": 1,
            "objects": self.objects,
            "comments": [],
            "backgroundColor": self.background,
        }

    def save(self, path: str):
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
            for asset, src in self.assets.items():
                z.write(src, asset)
            z.writestr("data.json", json.dumps(self.to_json(), ensure_ascii=False))
        return path


# ------------------------------------------------------------------ чтение
def load(path: str) -> dict:
    """Читает .holst и возвращает разобранный data.json."""
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read("data.json"))


def object_text(obj: dict) -> str:
    """Достаёт плоский текст из jsonState объекта."""
    state = obj.get("jsonState")
    if not state:
        return ""
    lines = []
    for node in json.loads(state["children"]):
        for child in node["children"]:
            lines.append("".join(leaf.get("text", "") for leaf in child["children"]))
    return "\n".join(lines)
