# Формат .holst

Восстановлен по штатной выгрузке доски из Холста (holst.so) и подтверждён
экспериментально: сгенерированный по этому описанию файл открывается со всеми
объектами, связями и форматированием. Официальной спецификации нет, поэтому
формат может измениться без предупреждения.

## Контейнер

`.holst` — ZIP **без сжатия** (`ZIP_STORED`), плоская структура:

```
data.json
<uuid>.png      ← ассеты: картинки, вложенные файлы
<uuid>.pdf
```

```json
{
  "boardName": "…",
  "version": 1,
  "backgroundColor": 16119285,
  "comments": [],
  "objects": [ … ]
}
```

## Объекты

Все объекты лежат **плоским списком**; иерархия задаётся только через `parentId`.
Координаты детей — **абсолютные**, а не относительно родителя.

Обязательные поля каждого объекта:

| Поле | Тип | Смысл |
|---|---|---|
| `id` | uuid-строка | уникален в пределах доски |
| `type` | строка | см. таблицу типов |
| `position` | `{x, y}` | float |
| `bounds` | `{x, y, width, height, type: 1}` | габариты |
| `zIndex` | float | должен расти; библиотека шагает по 1000 |
| `created` | `{a: <id автора>, t: <ms>}` | |
| `parentId` | uuid или `null` | принадлежность фрейму/группе |
| `updated` | `null` | |

Цвета — десятичный `int` (`0xRRGGBB`). Заливка — объект: `{"color": 16777215, "opacity": 1}`.
Холст принимает и строковые токены палитры (`"yellow4"`, `"gray3"`), но int надёжнее.

## Типы объектов

| type | Ключевые поля |
|---|---|
| `frame` | `labelText`, `fillColor`, `isContentHidden` |
| `sticker` | `textScale`, `fillColor`, `jsonState`, `reactions: []` |
| `simple-text` | `textScale`, `fixedWidth`, `fontFamily`, `textColor` |
| `shape` | `shapeType`: `square` / `ellipse` / `basic-star`; `fontSize`, `strokeStyle` |
| `arrow` | `start`/`end` с `objectId` + `relativePoint` (0..1) для привязки к объекту; `arrowType`: `straight`/`curved`/`elbow`; наконечники `none`/`triangle-filled`/`arc`/`miro` |
| `image` | `name` = имя файла в архиве; опц. `cropTransform`, `linkTo` |
| `file` | вложенный PDF: `fileName`, `pagesInfo`, `pinnedPage`, `displayType: "content"` |
| `link` | `link` + `linkInfo` (title, description, faviconKey) |
| `stamp` | `data: {"type": "textStamp", "text": "👍"}` |
| `drawing` | `path` — плоская строка `"x1,y1,x2,y2,…"`, `algorithm`: `lazy` (сглаживает) / `simple` |
| `group` | только `bounds` + `ignoreZIndex: true`; дети ссылаются через `parentId` |
| `phosphor-icon` | иконка из встроенного набора; библиотекой не создаётся, но переживает точечную правку файла |
| `table` / `table-cell` | таблица хранит `row-N` / `column-N` / `merge-R-C`; ячейки — отдельные объекты с `rowId`/`columnId`. Библиотекой не покрыто — собирать вручную по образцу из существующей выгрузки |

Ссылку на объект вешает поле `linkTo` со строкой URL. Документировано для `image`;
на фигурах и тексте работает так же (`shape(link=...)`, `text(link=...)`), но
проверяй в редакторе.

Шрифты: `OpenSans` (основной), `Roboto`, `Bangers`, `Graduate`, `NotoSans`.
Если доска делается в чьём-то фирменном стиле, шрифт задавай явно во всех вызовах:
смешение двух гарнитур на доске заметно сразу.

## Две неочевидные вещи

**1. `textScale` — множитель всего объекта, а не кегль.**
Фактический размер = `width × textScale`, и `bounds` обязан это учитывать.
У стикера `width: 192` — «логический» размер. Отсюда: стикер нельзя растягивать
как баннер, `scale` тянет и ширину, и высоту.

**2. Текст сериализуется дважды.**
`jsonState.children` — это *строка*, внутри которой JSON-массив Slate-подобных
узлов. Каждый абзац обёрнут в `wrapper` с UUID-ключом:

```json
{"type": "wrapper", "key": "<uuid>", "children": [
  {"type": "paragraph", "key": "<uuid>", "children": [
    {"text": "Привет", "bold": true, "color": 1710618}
  ]}
]}
```

Типы блоков: `paragraph`, `initial` (пустая строка), `ul-list-item`, `ol-list-item`.
Свойства листа: `bold`, `italic`, `color`.

## Чтение доски

```python
from holst import load, object_text

data = load("board.holst")
for o in data["objects"]:
    if o["type"] == "frame":
        print(o["labelText"])
    elif o.get("jsonState"):
        print("   ", object_text(o))
```

Или без библиотеки:

```python
import zipfile, json
d = json.loads(zipfile.ZipFile("board.holst").read("data.json"))
for o in d["objects"]:
    if o.get("jsonState"):
        nodes = json.loads(o["jsonState"]["children"])
```

Правка существующей выгрузки, снятие чужого шаблона и разбор гистограмм стилей —
в [`editing.md`](editing.md).

## Ориентиры по вёрстке

- Кадр 16:9 — `4800 × 2700`, поля 200.
- Стикер: 192×192 (широкий 384×192), зазор 24. Размер стикера считай от свободной
  области: `min((w - gap*(cols-1))/cols, (h - gap*(rows-1))/rows)` — так сетка не
  вылезет из своего блока.
- Между кадрами оставляй 400+ по горизонтали, иначе они слипаются.
- Холст сам подгоняет кегль текста внутри стикера под его длину — короткие подписи
  выглядят крупнее длинных, это штатно.
- `zIndex` должен расти; библиотека делает это сама с шагом 1000.
