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

## Цвета

Два равноправных вида, оба оборачиваются в объект
`{"color": <int|токен>, "opacity": 1}`:

- **int** `0xRRGGBB` — произвольный цвет, единственный способ задать свой.
- **строковый токен палитры Холста** — шкала в духе Radix: имя цвета плюс номер
  ступени. Встречались `white1`, `white3`, `white6`, `gray3`, `gray7`, `gray8`,
  `gray10`, `gray12`, `yellow4`, `pink10`, `red10`, `violet10`. Полный список
  неизвестен, но схема очевидна. Токен точнее попадает в фирменную палитру.

В библиотеке токены доступны как `WHITE3`, `GRAY12`, `RED10` и так далее.

## Типы объектов

| type | Ключевые поля |
|---|---|
| `frame` | `labelText`, `fillColor`, `isContentHidden` |
| `sticker` | `textScale`, `fillColor`, `jsonState`, `reactions: []` |
| `simple-text` | `textScale`, `fixedWidth`, `textColor`; `fontFamily` выставлять не нужно |
| `shape` | `shapeType` — см. ниже; `fontSize` — **абсолютный** кегль в единицах доски (если поле не задать, Холст подберёт кегль сам); `strokeWidth` тоже в единицах доски, на кадре 4800 рабочие значения 4–12 |
| `arrow` | `start`/`end` с `objectId` + `relativePoint` (0..1) для привязки к объекту; `arrowType`: `straight`/`curved`/`elbow`; наконечники `none`/`triangle-filled`/`arc`/`miro` |
| `image` | `name` = имя файла в архиве (не обязано совпадать с `id`, на один файл могут ссылаться несколько объектов); `naturalWidth`/`naturalHeight` — пиксельный размер исходника, `imageType`, `originalName`; опц. `cropTransform`, `linkTo` |
| `flip-card` | логический размер `220×320`, `bounds` = логический × `scale`; `side`: `front`/`back`; `frontDocumentId`/`backDocumentId` — просто uuid; текст в `frontJsonState`/`backJsonState` |
| `file` | вложенный PDF: `fileName`, `pagesInfo`, `pinnedPage`, `displayType: "content"` |
| `link` | `link`, `displayType: 1`, `linkInfo` (title, description, imageKey, faviconKey). Логическая ширина **300**, высота зависит от описания: 111 в одну строку, +22,5 за каждую следующую (≈46 знаков в строке). Промахнётесь — Холст переверстает сам, разъедется только рамка выделения |
| `reaction-stamp` | `stampKey`: `like`/`dislike`/`heart`/`star`/`check`/`cross`/`+1`/`figma-question`; логический размер 60, `rotation`. Необязательный `stickyPosition` — `{parentId, constraints: {x,y: "normalized"}, x, y}` — прилепляет штамп к объекту в долях его габаритов |
| `card` | документ-карточка: `colorToken`, `fixedSize: false`, `jsonState` с заголовками `heading-one`/`two`/`three` |
| `task-card` | `titleJsonState`, `index` (порядок), `assigneeIds`, `scale`; внутри канбана — `parentId` доски, `columnId`, `swimlaneId` и ширина 338 вместо 320 |
| `kanban` | `columns: [{title, index, id}]`, `swimlanes: [{title, index, id}]`. Карточки — отдельные `task-card`, связь по id колонки |
| `mind-map-node` | `nodeColor` (обычно с `opacity` 0.1), `nodeType`, `strokeStyle`, `jsonState`. Узлы соединяются обычными стрелками |
| `code` | `clonedTextValue` — просто строка кода, `theme`: `light`/`dark`, `scale` |
| `dice` | `faces`, `value`, `spinTime`, `rotation`; логический размер 240 |
| `spinner-wheel` | `items: [{id, label}]`, `mode`, `selectedItemId`, `excludedItemIds`, `wheelRotation`; логический размер 360 |
| `sticker-stack` | пачка стикеров: `width`/`height` 192, но `bounds` 232×288 |
| `phosphor-icon` | `iconName`, `weight`: `thin`/`light`/`regular`/`bold`/`fill`/`duotone`, `fillColor` |
| `drawing` | `path` — плоская строка `"x1,y1,x2,y2,…"`, `algorithm`: `lazy` (сглаживает) / `simple` |
| `group` | только `bounds` + `ignoreZIndex: true`; дети ссылаются через `parentId` |
| `phosphor-icon` | иконка из встроенного набора; библиотекой не создаётся, но переживает точечную правку файла |
| `table` / `table-cell` | см. ниже |
| `file` | `fileName` (имя в архиве), `displayFileName`, `fileSize`, `fileType` — настоящий MIME, `pagesInfo`, `pageSize` (размер страницы исходника), `displayType: "content"` |

## Таблица

Таблица — это объект `table` плюс отдельные объекты `table-cell` с `parentId`
таблицы. Порядок строк и колонок задаётся «дробным индексом»: шаг `2**40`
(1099511627776), то есть у N-й колонки `index = N * 2**40`. Такая нумерация
позволяет вставить строку между двумя существующими, не перенумеровывая всё.

```json
{"type": "table", "strokeColor": {…}, "fillColor": {"color": null, "opacity": 1},
 "fillColorIndex": 5,
 "column-1": {"index": 1099511627776, "width": 240},
 "column-2": {"index": 2199023255552, "width": 240},
 "row-1": {"index": 1099511627776, "height": 60, "minHeight": 60}}
```

У колонки и строки могут быть `horizontalAlign` / `verticalAlign` (плюс
парные `*Index`) и `textRotation` — так делается «шапка» с вертикальным текстом.

Ячейка: `position` всегда `{0, 0}`, а `bounds` — абсолютные координаты на доске.

```json
{"type": "table-cell", "parentId": "<id таблицы>", "documentId": "<uuid>",
 "rowId": 1, "columnId": 1, "isFake": false, "countRow": 1, "countColumn": 1,
 "rows": [{"index": 1099511627776, "height": 60, "minHeight": 60, "rowId": 1}],
 "columns": [{"index": 1099511627776, "width": 240, "columnId": 1}],
 "tableStyles": {"strokeColor": {…}, "fillColor": {…}, "fillColorIndex": 1},
 "fillColor": {…}, "jsonState": {…}}
```

Объединённые ячейки хранятся как `merge-R-C` — библиотекой не покрыто.

Ссылку на объект вешает поле `linkTo` со строкой URL. Документировано для `image`;
на фигурах и тексте работает так же (`shape(link=...)`, `text(link=...)`), но
проверяй в редакторе.

Шрифты: `OpenSans` (основной), `Roboto`, `Bangers`, `Graduate`, `NotoSans`.
Если доска делается в чьём-то фирменном стиле, шрифт задавай явно во всех вызовах:
смешение двух гарнитур на доске заметно сразу.

## Геометрия текста

Самое неочевидное в формате. Холст набирает `simple-text` шрифтом **Inter**,
и внутри объекта кегль всегда один и тот же — масштабируется весь блок целиком:

- Внутренний кегль всегда **14**, внутренняя высота строки — **21**
  (те же единицы, что и поле `width`). Отсюда интерлиньяж ровно **1,5**.
- Фактический кегль на доске = `14 × textScale`, высота строки = `21 × textScale`.
- Ширина колонки набора на доске = `width × textScale`, то есть
  `width = ширина_в_единицах_доски / textScale`.
- `bounds.height` = `число_строк × 21 × textScale`.
- `bounds.width` = `(width + 0.5) × textScale` при `fixedWidth: true`.
  Без `fixedWidth` перенос не делается вовсе, а `bounds.width` растёт по самой
  длинной строке.

Чтобы посчитать число строк, нужно повторить перенос Холста — для этого в
`scripts/inter_widths.json` лежит таблица ширин глифов Inter (Regular и SemiBold),
а в библиотеке есть `ems()` и `text_lines()`.

**Шрифт задавать не нужно.** В штатной выгрузке поля `fontFamily` у текста нет:
Холст набирает всю доску своим Inter. Если выставить `fontFamily` явно, этот блок
будет набран другой гарнитурой, чем вся остальная доска.

**`textScale` у остальных типов — множитель всего объекта, а не кегль.**
Итоговый размер = логический × `textScale`, и `bounds` обязан это учитывать.
У стикера логический размер `192×192` (широкий — `384×192`), у флип-карты
`220×320`, у карточки ссылки ширина `300`. Отсюда: стикер нельзя растягивать
как баннер — масштаб тянет и ширину, и высоту.

**`bounds` — не декорация.** Холст берёт из него рамку выделения и вписывание
во фрейм. Разъехался с фактическим размером — объект ведёт себя странно.

## Текст: двойная сериализация

`jsonState.children` — это *строка*, внутри которой JSON-массив Slate-подобных
узлов. Каждый абзац обёрнут в `wrapper` с UUID-ключом:

```json
[{"type": "wrapper", "key": "<uuid>", "children": [
  {"type": "paragraph", "key": "<uuid>", "children": [
    {"bold": true, "text": "Цель: "},
    {"text": "сгенерировать идеи"}
  ]}
]}]
```

Типы блоков: `paragraph`, `initial` (пустая строка), `ul-list-item`, `ol-list-item`.
У `ol-list-item` есть необязательный `counter` — им нумерация начинается заново;
ставь `counter: 1` первому пункту, иначе список продолжит нумерацию предыдущего
списка в том же объекте.

Свойства листа: `bold`, `italic`, `color` (int или токен палитры).

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

## Комментарии

Лежат отдельным массивом `comments` на верхнем уровне, а не среди объектов.
`target.type` различает привязку: `1` — к объекту (`targetId` плюс `point`
в долях его габаритов, 0…1), `2` — к точке на доске (`point` в абсолютных
координатах, без `targetId`).

```json
{"target": {"type": 2, "point": {"x": 1767.3, "y": 6142.6}},
 "content": [ …те же wrapper/paragraph, что в jsonState… ],
 "resolved": false, "root": true, "mentions": [],
 "authorId": "<uuid>", "createdAt": 1788511962980.5, "id": "bxVxp"}
```

Генератор всегда пишет `comments: []`.

## Формы `shape`

Их 63. Базовые (константа `SHAPES_BASIC` в библиотеке):

`square`, `roundedRectangle`, `ellipse`, `triangle`, `invertedTriangle`,
`diamond`, `rightParallelogram`, `leftParallelogram`, `basic-star`,
`basic-pentagon`, `basic-hexagon`, `basic-octagon`, `basic-trapezoid`,
`basic-cross`, `basic-cloud`, `basic-speech-bubble`, `basic-arrow-right`,
`basic-arrow-left`, `basic-arrow-left-right`.

Блок-схемы: `flowchart-process`, `-decision`, `-terminator`,
`-predefined-process`, `-document`, `-multiple-documents`, `-manual-input`,
`-preparation`, `-data`, `-database`, `-direct-access-storage`,
`-internal-storage`, `-manual-operation`, `-delay`, `-stored-data`, `-merge`,
`-connector`, `-or`, `-summing-junction`, `-display`, `-off-page-connector`,
`-left-curly-brace-annotation`, `-right-curly-brace-annotation`, `-comment`,
`-note`.

BPMN: `bpmn-task`, `-transaction`, `-event-subprocess`, `-call-activity`,
`-event-start`, `-event-start-non-interrupting`, `-event-intermediate`,
`-event-intermediate-non-interrupting`, `-event-end`, `-conversation`,
`-call-conversation`, `-gateway`, `-data-object`, `-data-store`, `-empty-pool`,
`-group`, `-annotation`, `-message`.

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
