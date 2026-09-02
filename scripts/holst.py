"""holst.py — генератор .holst файлов (доски Холст / holst.so).

Часть проекта AI can Holst: https://github.com/sirponch-hub/aicanholst
Copyright (c) 2026 Mikhail Podurets. Лицензия CC BY-NC-SA 4.0 — см. LICENSE.

Формат восстановлен по штатной выгрузке доски и подтверждён экспериментально.
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

# Цвета — десятичный int (0xRRGGBB) либо строковый токен палитры Холста
# (см. ниже). Токен точнее попадает в фирменную палитру приложения,
# int — единственный способ задать произвольный цвет.
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

# Строковые токены палитры Холста. Проверены только эти; для произвольного
# цвета используй int 0xRRGGBB.
WHITE3, WHITE6 = "white3", "white6"
GRAY3, GRAY12 = "gray3", "gray12"
PINK10, RED10, VIOLET10 = "pink10", "red10", "violet10"

# Логические размеры масштабируемых объектов: итоговый = логический * scale.
STICKER, STICKER_WIDE = 192.0, 384.0
CARD_W, CARD_H = 220.0, 320.0       # флип-карта
LINK_W = 300.0                      # карточка ссылки
LINK_H_BASE = 111.0                 # высота при описании в одну строку
LINK_LINE = 22.5                    # прибавка за каждую следующую строку
LINK_CPL = 46                       # знаков в строке описания

# Холст набирает доску своим шрифтом (Inter). Выставлять fontFamily нужно
# только если вы сознательно хотите другую гарнитуру.
DEFAULT_FONT = None

# ------------------------------------------------------------------- кадр
SLIDE_W, SLIDE_H = 4800.0, 2700.0   # кадр 16:9 — базовая единица доски
PAD = 200.0                         # поле кадра
GAP_X = 420.0                       # между кадрами в строке
GAP_Y = 460.0                       # между строками
GAP_MODULE = 900.0                  # между модулями
GAP_DAY = 2400.0                    # между днями/разделами
CONTENT_W = SLIDE_W - 2 * PAD
TEXT_COL = 3000.0                   # комфортная мера набора (≈60 знаков)

# ---------------------------------------------------------------- типографика
#
# Холст набирает simple-text шрифтом Inter: внутренний кегль всегда 14,
# внутренняя высота строки 21, а textScale масштабирует блок целиком.
# Отсюда фактический кегль на доске = 14 * textScale, высота строки —
# 21 * textScale, то есть интерлиньяж ровно 1.5.

FS_INTERNAL = 14.0              # внутренний кегль simple-text (до textScale)
LINE_INTERNAL = 21.0            # внутренняя высота строки
LINE_H = LINE_INTERNAL / FS_INTERNAL    # 1.5
BOX_PAD = 0.6                   # вертикальные поля внутри фигуры, в долях кегля
FS_FLOOR = 60                   # мельче — нечитаемо на кадре 4800x2700

# textScale для ролей текста на кадре высотой 2700.
# Фактический кегль = 14 * scale; доля высоты кадра указана рядом.
TITLE = 13.0                    # заголовок кадра   → 182 (6.7%)
LEAD = 7.0                      # лид, подзаголовок → 98  (3.6%)
BODY = 6.0                      # основной текст    → 84  (3.1%)
SMALL = 4.6                     # подписи           → 64  (2.4%)
SCALE_FLOOR = 4.0               # пол читаемости    → 56  (2.1%)

# Метрика Inter: ширины глифов в em, снятые с Inter-Regular / Inter-SemiBold.
# Нужна, чтобы предсказать перенос строк и посчитать bounds.
#
# Таблица inter_widths.json и модель геометрии текста (кегль 14, строка 21,
# bounds.width = (width + 0.5) * textScale) взяты из проекта holst-board
# Дмитрия Соловьёва — https://github.com/soloveev/holst-board, CC BY-NC-SA 4.0.
# Он выверил их по PDF-экспорту доски, где пункт PDF равен единице доски.
_WIDTHS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "inter_widths.json")
try:
    with open(_WIDTHS_PATH, encoding="utf-8") as _f:
        _W = json.load(_f)
    REGULAR, SEMIBOLD = _W["regular"], _W["semibold"]
except (OSError, ValueError, KeyError):      # pragma: no cover
    REGULAR = SEMIBOLD = {}

_FB_REG = sum(REGULAR.values()) / len(REGULAR) if REGULAR else 0.55
_FB_SB = sum(SEMIBOLD.values()) / len(SEMIBOLD) if SEMIBOLD else 0.58


def ems(s, bold=False):
    """Ширина строки в em по метрике Inter."""
    table, fallback = (SEMIBOLD, _FB_SB) if bold else (REGULAR, _FB_REG)
    return sum(table.get(ch, fallback) for ch in str(s))


def text_width(text, fs, bold=False):
    """Ширина строки в тех же единицах, что и кегль fs."""
    return ems(text, bold) * fs


def text_lines(text, width, fs, bold=False):
    """Сколько строк займёт текст при данной ширине и кегле.
    width и fs — в одних единицах (доски либо внутренних)."""
    if width <= 0:
        return max(1, len(str(text).split("\n")))
    total = 0
    for para in str(text).split("\n"):
        words, cur, lines = para.split(" "), 0.0, 1
        for i, word in enumerate(words):
            adv = text_width(word, fs, bold)
            space = text_width(" ", fs, bold) if i else 0.0
            if cur and cur + space + adv > width:
                lines += 1
                cur = adv
            else:
                cur += space + adv
        total += lines
    return total


def box_h(text, w, fs, minimum=0, bold=False):
    """Высота, которая нужна фигуре шириной w, чтобы вместить текст кеглем fs.
    Считай высоту полосы отсюда, а не подгоняй текст под заданную высоту."""
    if not text:
        return minimum
    lines = text_lines(text, w - fs * 0.6, fs, bold)
    return max(minimum, lines * fs * LINE_H + fs * BOX_PAD)


def text_height(text, width_units, scale, bold=False):
    """Высота блока simple-text в единицах доски."""
    lines = text_lines(text, width_units, FS_INTERNAL * scale, bold)
    return lines * LINE_INTERNAL * scale


def fit_scale(text, width, budget, start=TITLE, floor=SCALE_FLOOR, step=0.2,
              bold=False):
    """Уменьшает textScale, пока блок не уложится в высоту budget.
    width и budget — в единицах доски. Ниже floor не опускается."""
    sc = start
    while sc - step >= floor and text_height(text, width, sc, bold) > budget:
        sc -= step
    return round(sc, 4)


def fit_fs(text, w, h, fs, floor=FS_FLOOR, step=4, bold=False):
    """Уменьшает font_size фигуры, пока текст не уложится в её высоту.
    Ниже floor не опускается — дальше растите фигуру (см. shape(grow=True))."""
    while fs - step >= floor and box_h(text, w, fs, bold=bold) > h:
        fs -= step
    return fs


def grid_size(cols, rows, w, h, gap=24):
    """Сторона квадратного стикера, вписанного в область w x h."""
    return max(60, min((w - gap * (cols - 1)) / cols, (h - gap * (rows - 1)) / rows))


def image_size(path):
    """Размер картинки в пикселях. Pillow, если есть; иначе — из заголовка."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except ImportError:
        pass
    with open(path, "rb") as fh:
        head = fh.read(26)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return (int.from_bytes(head[16:20], "big"),
                    int.from_bytes(head[20:24], "big"))
        fh.seek(2)                                   # JPEG: ищем SOF-маркер
        while True:
            byte = fh.read(1)
            while byte and byte != b"\xff":
                byte = fh.read(1)
            marker = fh.read(1)
            if not marker:
                break
            if 0xC0 <= marker[0] <= 0xCF and marker[0] not in (0xC4, 0xC8, 0xCC):
                fh.read(3)
                h = int.from_bytes(fh.read(2), "big")
                w = int.from_bytes(fh.read(2), "big")
                return w, h
            length = int.from_bytes(fh.read(2), "big")
            fh.read(length - 2)
    raise ValueError("Не удалось определить размер картинки: %s" % path)


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> int:
    return int(time.time() * 1000)


def _color(c, opacity: float = 1.0):
    return {"color": c, "opacity": opacity}


def _pid(parent):
    if parent is None:
        return None
    if isinstance(parent, Slide):
        return parent.frame["id"]
    return parent["id"] if isinstance(parent, dict) else parent


# --------------------------------------------------------- разметка текста
#
# Внутри text/sticker/shape работает мини-markdown:
#   **жирный**          → bold
#   *курсив*            → italic
#   {red10|цветной}     → color (токен палитры или 0xRRGGBB)
#   \n                  → новый абзац

def parse_inline(s):
    """'обычный **жирный** текст' → [(текст, {марка: значение}), …]"""
    out, buf, i, marks = [], "", 0, {}

    def flush():
        nonlocal buf
        if buf:
            out.append((buf, dict(marks)))
            buf = ""

    s = str(s)
    while i < len(s):
        if s.startswith("**", i):
            flush()
            if marks.pop("bold", None) is None:
                marks["bold"] = True
            i += 2
        elif s[i] == "*":
            flush()
            if marks.pop("italic", None) is None:
                marks["italic"] = True
            i += 1
        elif s[i] == "{" and "}" in s[i:] and "|" in s[i:s.index("}", i)]:
            close = s.index("}", i)
            color, txt = s[i + 1:close].split("|", 1)
            color = color.strip()
            color = int(color, 0) if color.startswith("0x") else color
            flush()
            out.append((txt, dict(marks, color=color)))
            i = close + 1
        else:
            buf += s[i]
            i += 1
    flush()
    return out or [("", {})]


def _leaf(text, marks):
    leaf = {}
    for mark in ("bold", "italic"):
        if marks.get(mark):
            leaf[mark] = True
    if marks.get("color") is not None:
        leaf["color"] = marks["color"]
    leaf["text"] = text
    return leaf


def _rich(text, bold=False, italic=False, color=None, bullets=False,
          block=None, markdown=True):
    """Строит jsonState. Абзацы делятся по \\n.

    block: paragraph | ul-list-item | ol-list-item | initial.
    Первому пункту нумерованного списка проставляется counter: 1, иначе
    нумерация продолжит предыдущий список в том же объекте.
    """
    base = {}
    if bold:
        base["bold"] = True
    if italic:
        base["italic"] = True
    if color is not None:
        base["color"] = color

    if block is None:
        block = "ul-list-item" if bullets else "paragraph"

    nodes, numbered = [], False
    for line in str(text).split("\n"):
        runs = parse_inline(line) if markdown else [(line, {})]
        node_type = block if line.strip() else "initial"
        node = {
            "type": node_type,
            "key": _uid(),
            "children": [_leaf(t, dict(base, **m)) for t, m in runs],
        }
        if node_type == "ol-list-item" and not numbered:
            node["counter"] = 1
            numbered = True
        nodes.append({"type": "wrapper", "key": _uid(), "children": [node]})
    return {"children": json.dumps(nodes, ensure_ascii=False)}


def plain_text(text, markdown=True):
    """Текст без разметки — для расчёта ширины и переноса."""
    if not markdown:
        return str(text)
    return "\n".join("".join(t for t, _ in parse_inline(line))
                     for line in str(text).split("\n"))


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
        self._col = 0                      # курсор сетки кадров
        self._row = 0
        self._row_y = 0.0
        self._row_h = 0.0

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

    def slide(self, x, y, label="Slide", fill=WHITE, w=SLIDE_W):
        """Кадр 16:9 — базовая единица доски. Высота считается сама.
        Возвращает сам фрейм; курсорную обёртку даёт page()."""
        return self.frame(x, y, w, w * 9 / 16, label, fill=fill)

    def page(self, label="", col=None, row=None, fill=WHITE, w=SLIDE_W,
             pad=PAD):
        """Кадр 16:9 на следующем месте сетки, с вертикальным курсором.

        Кадры кладутся строкой слева направо; new_row() переводит на новую.
        Возвращает Slide — у него есть title/body/bullets/gap/columns.
        """
        if col is not None:
            self._col = col
        if row is not None:
            self._row = row
            self._row_y = row * (SLIDE_H + GAP_Y)
        x = self._col * (w + GAP_X)
        y = self._row_y
        self._col += 1
        h = w * 9 / 16
        self._row_h = max(self._row_h, h)
        return Slide(self, self.frame(x, y, w, h, label, fill=fill), pad=pad)

    def new_row(self, gap=GAP_Y):
        """Следующий page() начнёт новую строку кадров."""
        self._row_y += self._row_h + gap
        self._row_h = 0.0
        self._col = 0
        self._row += 1
        return self

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

    def text(self, x, y, text="", scale=BODY, width=None, width_units=None,
             color=DARK_GRAY, fill=None, halign="left", font=None,
             fixed_width=True, parent=None, bold=False, italic=False,
             bullets=False, block=None, rotation=0, link=None, markdown=True):
        """Свободный текст. Фактический кегль = 14 * scale, высота строки —
        21 * scale. `width` — логическая ширина набора (её и хранит Холст),
        `width_units` — та же ширина в единицах доски (= width * scale);
        задавай что-то одно.

        Шрифт по умолчанию не выставляется: Холст набирает доску своим Inter,
        а явный fontFamily даст текст другой гарнитурой, чем вся остальная доска.
        """
        if width_units is not None:
            width = width_units / scale
        elif width is None:
            width = TEXT_COL / scale

        flat = plain_text(text, markdown)
        lines = text_lines(flat, width, FS_INTERNAL, bold) if fixed_width \
            else len(flat.split("\n"))
        if fixed_width:
            bw = width + 0.5
        else:
            bw = max(ems(l, bold) * FS_INTERNAL for l in flat.split("\n")) + 0.5

        o = self._base("simple-text", x, y, bw * scale,
                       lines * LINE_INTERNAL * scale, parent)
        o.update({
            "width": round(float(width), 2),
            "textScale": float(scale),
            "textBackgroundColor": {"opacity": 1, "color": None},
            "textColor": _color(color),
            "fixedWidth": bool(fixed_width),
            "horizontalAlign": halign,
            "rotation": rotation,
            "jsonState": _rich(text, bold=bold, italic=italic, bullets=bullets,
                               block=block, markdown=markdown),
        })
        if font:
            o["fontFamily"] = font
        if fill is not None:
            o["fillColor"] = _color(fill)
        if link:
            o["linkTo"] = link
        return self._add(o)

    def shape(self, x, y, width, height, text="", shape_type="square", fill=WHITE,
              stroke=DARK_GRAY, stroke_width=2, stroke_opacity=1.0, stroke_style="solid",
              text_color=BLACK, font_size=26, font=DEFAULT_FONT, halign="center",
              valign="center", rotation=0, parent=None, bold=False, autofit=True,
              grow=True, link=None):
        """shape_type: square | ellipse | basic-star.
        autofit ужимает кегль до пола, grow дорастит высоту, если и так не влезает.
        Обрезанного текста быть не должно."""
        fs = font_size
        flat = plain_text(text)
        if text and autofit:
            fs = fit_fs(flat, width, height, font_size, bold=bold)
            if grow:
                height = max(height, box_h(flat, width, fs, bold=bold))
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
        if link:
            o["linkTo"] = link
        return self._add(o)

    def image(self, x, y, path, width=None, height=None, parent=None, link_to=None):
        """Кладёт файл в архив под <uuid>.<ext> и создаёт объект image.
        Пропорции сохраняются: задай одну сторону, вторая посчитается сама."""
        if not os.path.isfile(path):
            raise FileNotFoundError("Картинки нет на диске: %s" % path)
        ext = os.path.splitext(path)[1].lower() or ".png"
        nw, nh = image_size(path)
        if width is None and height is None:
            width, height = nw, nh
        elif width is None:
            width = height * nw / nh
        elif height is None:
            height = width * nh / nw
        asset = _uid() + ext
        self.assets[asset] = path
        o = self._base("image", x, y, width, height, parent)
        o.update({
            "width": float(width),
            "height": float(height),
            "naturalWidth": nw,
            "naturalHeight": nh,
            "imageType": "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png",
            "originalName": os.path.basename(path),
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

    def image_fit(self, x, y, box_w, box_h_, path, parent=None, link_to=None):
        """Картинка, вписанная в область с сохранением пропорций и центрированием.
        Параметр назван box_h_, чтобы не перекрывать функцию box_h()."""
        iw, ih = image_size(path)
        k = min(box_w / iw, box_h_ / ih)
        pw, ph = iw * k, ih * k
        return self.image(x + (box_w - pw) / 2, y + (box_h_ - ph) / 2, path,
                          width=pw, height=ph, parent=parent, link_to=link_to)

    def flip_card(self, x, y, front="", back="", scale=3.0, side="front",
                  parent=None):
        """Карточка с двумя сторонами. Логический размер 220x320,
        итоговый = логический * scale."""
        o = self._base("flip-card", x, y, CARD_W * scale, CARD_H * scale, parent)
        o.update({
            "width": CARD_W,
            "height": CARD_H,
            "scale": float(scale),
            "side": side,
            "frontDocumentId": _uid(),
            "backDocumentId": _uid(),
            "frontJsonState": _rich(front),
            "backJsonState": _rich(back),
        })
        return self._add(o)

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

    def link(self, x, y, url, title="", description="", scale=4.0, parent=None,
             height_units=None):
        """Карточка ссылки. Логическая ширина всегда 300, высота зависит от
        того, во сколько строк ляжет описание (≈46 знаков в строке).
        Если промахнуться, Холст переверстает карточку сам — разъедется
        только рамка выделения."""
        if height_units is None:
            lines = max(1, -(-len(description) // LINK_CPL)) if description else 1
            height_units = LINK_H_BASE + LINK_LINE * (lines - 1)
        o = self._base("link", x, y, LINK_W * scale, height_units * scale, parent)
        o.update({
            "link": url,
            "displayType": 1,
            "scale": float(scale),
            "linkInfo": {"link": url, "title": title, "description": description,
                         "imageKey": None, "faviconKey": None},
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


# ------------------------------------------------------- кадр с курсором

class Slide:
    """Обёртка над кадром: вертикальный курсор и раскладка по полям.

    Курсор ведут title / body / bullets / caption / gap — блоки встают друг
    под другом сами. Точное размещение по-прежнему доступно: s.left, s.y,
    s.rel(dx, dy) и проксирующие методы text / shape / sticker.
    """

    def __init__(self, board, frame, pad=PAD):
        self.b = board
        self.frame = frame
        self.pad = pad
        self.x = frame["position"]["x"]
        self.y = frame["position"]["y"]
        self.w = frame["width"]
        self.h = frame["height"]
        self.cursor = self.y + pad

    # -------------------------------------------------------- геометрия
    @property
    def content_w(self):
        return self.w - 2 * self.pad

    @property
    def left(self):
        return self.x + self.pad

    @property
    def bottom(self):
        return self.y + self.h - self.pad

    @property
    def free_h(self):
        """Сколько высоты осталось до нижнего поля кадра."""
        return self.bottom - self.cursor

    def rel(self, dx, dy):
        return self.x + dx, self.y + dy

    def gap(self, dy):
        self.cursor += dy
        return self

    def columns(self, n, gap=60.0):
        """Делит поле кадра на n колонок. Возвращает [(x, ширина), …]."""
        cw = (self.content_w - gap * (n - 1)) / n
        return [(self.left + i * (cw + gap), cw) for i in range(n)]

    # ---------------------------------------------------------- контент
    def title(self, text, scale=TITLE, width=None, gap=180.0, bold=True, **kw):
        """Заголовок кадра. Сам ужимается до двух строк своего кегля."""
        width = width or self.content_w
        sc = fit_scale(plain_text(text), width, LINE_INTERNAL * scale * 2,
                       start=scale, floor=SCALE_FLOOR + 2, bold=bold)
        return self._flow(text, sc, width, gap, None, bold=bold, **kw)

    def body(self, text, scale=BODY, width=TEXT_COL, gap=None, **kw):
        return self._flow(text, scale, width, gap, None, **kw)

    def bullets(self, items, scale=BODY, width=TEXT_COL, gap=None,
                ordered=False, **kw):
        text = items if isinstance(items, str) else "\n".join(items)
        block = "ol-list-item" if ordered else "ul-list-item"
        return self._flow(text, scale, width, gap, block, **kw)

    def caption(self, text, scale=SMALL, width=TEXT_COL, gap=None, **kw):
        return self._flow(text, scale, width, gap, None, **kw)

    def _flow(self, text, scale, width, gap, block, **kw):
        width = min(width, self.content_w)
        o = self.b.text(self.left, self.cursor, text, scale=scale,
                        width_units=width, block=block, parent=self, **kw)
        self.cursor = (o["bounds"]["y"] + o["bounds"]["height"]
                       + (LINE_INTERNAL * scale if gap is None else gap))
        return o

    # ------------------------------------------------------------ блоки
    def sticker_grid(self, texts, cols=4, color=YELLOW, gap=24.0, width=None,
                     wide=False, x=None, y=None, box_h_=None):
        """Сетка стикеров, вписанная в ширину и в остаток кадра по высоте.

        box_h_ — высота области, внутри которой сетку нужно отцентрировать;
        по умолчанию это всё свободное место до нижнего поля кадра. Если
        сетка не помещается, стикеры уменьшаются, а не вылезают из кадра.
        """
        width = width or self.content_w
        x0 = self.left if x is None else x
        y0 = self.cursor if y is None else y
        rows_used = math.ceil(len(texts) / cols) if texts else 0
        if not rows_used:
            return []

        logical_w = STICKER_WIDE if wide else STICKER
        scale = (width - gap * (cols - 1)) / cols / logical_w

        avail_h = box_h_ if box_h_ is not None else (self.bottom - y0 if y is None
                                                     else None)
        if avail_h and avail_h > 0:
            by_height = (avail_h - gap * (rows_used - 1)) / rows_used / STICKER
            scale = min(scale, by_height)

        cell_w, step = logical_w * scale, STICKER * scale + gap
        used_w = cols * cell_w + gap * (cols - 1)
        used_h = rows_used * step - gap
        x0 += max(0.0, (width - used_w) / 2)
        if box_h_:
            y0 += max(0.0, (box_h_ - used_h) / 2)

        out = [self.b.sticker(x0 + (i % cols) * (cell_w + gap),
                              y0 + (i // cols) * step, t, color=color,
                              width=logical_w, scale=scale, parent=self)
               for i, t in enumerate(texts)]
        if y is None:
            self.cursor = y0 + used_h + gap
        return out

    def empty_grid(self, cols, rows, color=YELLOW, **kw):
        """Сетка пустых стикеров под работу участников."""
        return self.sticker_grid([""] * (cols * rows), cols=cols, color=color, **kw)

    def image_fit(self, box_w, box_h_, path, gap=120.0, x=None, y=None):
        o = self.b.image_fit(self.left if x is None else x,
                             self.cursor if y is None else y,
                             box_w, box_h_, path, parent=self)
        if y is None:
            self.cursor += box_h_ + gap
        return o

    # ------------------------------- проксирование к доске с parent=self
    def text(self, x, y, *a, **kw):
        kw.setdefault("parent", self)
        return self.b.text(x, y, *a, **kw)

    def shape(self, x, y, w, h, *a, **kw):
        kw.setdefault("parent", self)
        return self.b.shape(x, y, w, h, *a, **kw)

    def sticker(self, x, y, *a, **kw):
        kw.setdefault("parent", self)
        return self.b.sticker(x, y, *a, **kw)

    def stamp(self, x, y, *a, **kw):
        kw.setdefault("parent", self)
        return self.b.stamp(x, y, *a, **kw)

    def image(self, x, y, *a, **kw):
        kw.setdefault("parent", self)
        return self.b.image(x, y, *a, **kw)


# ------------------------------------------------------------------ чтение
def load(path: str) -> dict:
    """Читает .holst и возвращает разобранный data.json."""
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read("data.json"))


def object_text(obj: dict) -> str:
    """Достаёт плоский текст объекта, включая обе стороны флип-карты."""
    lines = []
    for key in ("jsonState", "frontJsonState", "backJsonState"):
        state = obj.get(key)
        if not state:
            continue
        for node in json.loads(state["children"]):
            for child in node["children"]:
                lines.append("".join(leaf.get("text", "")
                                     for leaf in child["children"]))
    return "\n".join(lines)
