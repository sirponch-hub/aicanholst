Перед выдачей файла прогони **обе** проверки.

## 1. Схема и вместимость

Скрипт проверяет структуру архива, обязательные поля, `bounds`, выход за границы
кадра и слишком мелкий кегль. Запиши его в `validate.py` рядом с `holst.py`:

```python
import json, sys, zipfile
from holst import BOX_PAD, FS_INTERNAL, LINE_H, LINE_INTERNAL, text_lines

REQUIRED = ("id", "type", "position", "bounds", "zIndex", "created", "parentId")


def lines_of(o):
    st = o.get("jsonState")
    return ["".join(l.get("text", "") for l in ch["children"])
            for n in json.loads(st["children"]) for ch in n["children"]] if st else []


def need_h(o):
    ls = lines_of(o)
    if not any(ls):
        return 0
    if o["type"] == "simple-text":
        w = o["width"] if o.get("fixedWidth") else float("inf")
        return text_lines("\n".join(ls), w, FS_INTERNAL) * LINE_INTERNAL * o["textScale"]
    fs = FS_INTERNAL * o["textScale"] if o["type"] == "sticker" else o.get("fontSize", 30)
    pad = fs * BOX_PAD if o["type"] == "shape" else 0
    w = o["bounds"]["width"] - (fs * 0.6 if o["type"] == "shape" else 0)
    return text_lines("\n".join(ls), w, fs) * fs * LINE_H + pad


def check(path, edited=False):
    errors, warnings = [], []
    with zipfile.ZipFile(path) as z:
        for i in z.infolist():
            if i.compress_type != zipfile.ZIP_STORED:
                errors.append("Архив сжат — нужен ZIP_STORED")
                break
        d = json.loads(z.read("data.json"))
        assets = {i.filename for i in z.infolist()} - {"data.json"}

    frames = {o["id"]: o for o in d["objects"] if o["type"] == "frame"}
    ids = {o["id"] for o in d["objects"]}

    seen = {}
    for f in frames.values():
        seen[f.get("labelText", "")] = seen.get(f.get("labelText", ""), 0) + 1
    for label, n in seen.items():
        if n > 1:
            warnings.append("ДУБЛЬ ИМЕНИ КАДРА (%d): %s" % (n, label or "(без имени)"))

    for o in d["objects"]:
        miss = [f for f in REQUIRED if f not in o]
        if miss:
            errors.append("%s: нет полей %s" % (o.get("type"), ", ".join(miss)))
            continue
        if o["parentId"] and o["parentId"] not in ids:
            errors.append("%s: parentId в никуда" % o["type"])
        if o["type"] == "image" and o["name"] not in assets:
            errors.append("image: нет файла %s в архиве" % o["name"])
        # У текста рамка на полъединицы шире колонки набора. В файлах,
        # прошедших через редактор Холста, bounds пересчитан — не проверяем.
        exp = None
        if o["type"] == "sticker":
            exp = o["width"] * o["textScale"]
        elif o["type"] == "simple-text" and not edited and o.get("fixedWidth"):
            exp = (o["width"] + 0.5) * o["textScale"]
        if exp is not None and abs(o["bounds"]["width"] - exp) > 1:
            errors.append("%s: bounds.width %.0f != %.0f" % (o["type"],
                                                            o["bounds"]["width"], exp))

        if o["type"] not in ("sticker", "simple-text", "shape"):
            continue
        n = need_h(o)
        if n and o["type"] in ("shape", "sticker") and n > o["bounds"]["height"]:
            errors.append("НЕ ВЛЕЗАЕТ: %s" % (lines_of(o)[0][:40]))
        f = frames.get(o["parentId"])
        if not f:
            continue
        h = n if o["type"] == "simple-text" else max(o["bounds"]["height"], n)
        if o["bounds"]["y"] + h > f["bounds"]["y"] + f["bounds"]["height"] - 20:
            errors.append("НИЖЕ КАДРА [%s]: %s" % (f["labelText"], lines_of(o)[0][:40]))
        if o["bounds"]["x"] + o["bounds"]["width"] > f["bounds"]["x"] + f["bounds"]["width"]:
            errors.append("ШИРЕ КАДРА [%s]: %s" % (f["labelText"], lines_of(o)[0][:40]))
        fs = FS_INTERNAL * o["textScale"] if o["type"] != "shape" else o.get("fontSize", 30)
        if any(lines_of(o)) and fs < f["bounds"]["height"] * 0.02:
            warnings.append("МЕЛКИЙ КЕГЛЬ %.0f [%s]" % (fs, f["labelText"]))

    for w in warnings:
        print("⚠ ", w)
    for e in errors:
        print("✗ ", e)
    print("\n%d объектов, %d кадров — %s" % (len(d["objects"]), len(frames),
                                             "ОК" if not errors else "%d ошибок" % len(errors)))
    return not errors


if __name__ == "__main__":
    sys.exit(0 if check(sys.argv[1], "--edited" in sys.argv) else 1)
```

Правь доску, пока не станет чисто. Флаг `--edited` — для файлов, которые уже
открывались в Холсте: редактор пересчитывает `bounds` у текста по фактической
ширине, и расхождение там норма.

## 2. Картинка глазами

Напиши одноразовый рендер кадров в SVG: `frame`/`sticker`/`shape` как
`<rect>`/`<ellipse>` по `bounds` с заливкой `"#%06x" % color`, `arrow` как
`<line>`, `image` через `<image xlink:href="data:image/png;base64,…">` из архива,
текст из `jsonState`. **Строки переноси функцией `text_lines`/`ems` из библиотеки**,
иначе рендер соврёт именно там, где важно.

Переведи в PNG (`pip install cairosvg --break-system-packages -q`, затем
`cairosvg.svg2png(url=..., write_to=..., output_width=1800)`) и **посмотри глазами
несколько отдельных кадров, а не всю доску целиком**: доска из сотни кадров в общем
плане нечитаема. Бери самые плотные — таблицы, канвасы, кадры с длинным текстом
и со схемами.

Глазами проверяется то, что арифметика не ловит: композиция и выключка —
например, подпись, уехавшая от своей фигуры.
