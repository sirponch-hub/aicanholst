#!/usr/bin/env python3
"""Собирает автономный SKILL.md — один файл со всеми правилами и библиотекой.

Репозиторий разложен по файлам: SKILL.md ссылается на references/ и scripts/.
Но скилл, установленный в Claude как пользовательский, живёт одним файлом —
для него библиотеку и правила надо вклеить внутрь.

    python3 tools/build_standalone.py dist/SKILL.md

Метрика Inter вклеивается прореженной: латиница, кириллица и пунктуация.
Для отсутствующих глифов библиотека берёт среднюю ширину — так таблица
занимает вдвое меньше, а перенос считается так же точно на реальных текстах.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEEP = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    "0123456789 .,:;!?—–-()[]{}«»\"'/\\|@#$%&*+=<>~^_`…•→"
)


# Полная спецификация — references/format.md в репозитории. В автономную версию
# идёт короткая: библиотека закрывает всё, кроме таблиц и правки чужих выгрузок.
FORMAT_BRIEF = """# Формат в двух словах

`.holst` — ZIP **без сжатия** (`ZIP_STORED`), плоский, без папок: `data.json`
плюс ассеты с именами `<uuid>.<ext>`.

```json
{"boardName": "…", "version": 1, "backgroundColor": 16119285,
 "comments": [], "objects": [...]}
```

Объекты лежат **плоским списком**; иерархия — только через `parentId`,
координаты у детей **абсолютные**. У каждого объекта обязательны `id`, `type`,
`position`, `bounds`, `zIndex`, `created`, `parentId`.

Цвет — int `0xRRGGBB` либо строковый токен палитры Холста (`white3`, `gray3`,
`gray12`, `pink10`, `red10`, `violet10` — проверены только эти). Заливка и
обводка оборачиваются: `{"color": …, "opacity": 1}`.

**Геометрия текста.** Холст набирает `simple-text` шрифтом Inter: внутренний
кегль всегда 14, внутренняя высота строки 21, а `textScale` масштабирует блок
целиком. Отсюда:

- фактический кегль = `14 × textScale`, высота строки = `21 × textScale`
  (интерлиньяж ровно 1,5);
- ширина колонки набора = `width × textScale`;
- `bounds.height` = `число_строк × 21 × textScale`;
- `bounds.width` = `(width + 0.5) × textScale` при `fixedWidth: true`.

**`fontFamily` выставлять не нужно** — в штатной выгрузке его нет, Холст
набирает всю доску своим Inter. Явный шрифт даст блок чужой гарнитурой.

У остальных типов `textScale`/`scale` — множитель всего объекта: итоговый
размер = логический × масштаб, и `bounds` обязан это учитывать. Логические
размеры: стикер `192×192` (широкий `384×192`), флип-карта `220×320`,
карточка ссылки — ширина `300`, высота 111 плюс 22,5 за каждую строку описания.

**Текст сериализуется дважды**: `jsonState.children` — это *строка*, внутри
которой JSON-массив Slate-подобных узлов. Каждый абзац обёрнут в `wrapper`;
типы блоков `paragraph`, `initial` (пустой), `ul-list-item`, `ol-list-item`
(первому пункту нужен `counter: 1`, иначе нумерация продолжит предыдущий
список). Свойства листа: `bold`, `italic`, `color`.

**Типы объектов.** Библиотека покрывает все 21, что встречаются в выгрузке:
`frame`, `simple-text`, `sticker`, `sticker-stack`, `shape`, `image`, `card`,
`flip-card`, `task-card`, `kanban`, `table` + `table-cell`, `mind-map-node`,
`code`, `link`, `file`, `reaction-stamp`, `phosphor-icon`, `dice`,
`spinner-wheel`, `drawing`, `group`, `arrow`.

Что стоит помнить о каждом:

- `shape` — 63 формы: 19 базовых (`square`, `ellipse`, `diamond`,
  `basic-star`, `basic-cloud`, `basic-speech-bubble`…), 25 блок-схемных
  (`flowchart-process`, `flowchart-decision`…) и 18 BPMN (`bpmn-task`,
  `bpmn-gateway`…). `fontSize` и `strokeWidth` абсолютные, в единицах доски:
  на кадре 4800 рабочая обводка 4–12, двойка не видна.
- `reaction-stamp` — `stampKey`: `like`, `dislike`, `heart`, `star`, `check`,
  `cross`, `+1`, `figma-question`. Поле `stickyPosition` прилепляет штамп
  к объекту в долях его габаритов (`stamp(..., on=объект, at=(0.75, 0.75))`).
- `card` — документ с заголовками: `# `, `## `, `### ` разбираются в
  `heading-one/two/three`.
- `kanban` хранит колонки и дорожки, а карточки лежат отдельными `task-card`
  и связаны с колонкой через `columnId`, а не координатами.
- `table` — сам объект плюс отдельные `table-cell` с `parentId` таблицы;
  порядок строк и колонок задаётся «дробным индексом» с шагом 2⁴⁰.
  Объединённые ячейки (`merge-R-C`) не покрыты.
- `file` — `fileType` должен быть настоящим MIME, нужен `pageSize`.

Полная спецификация с полями каждого типа — `references/format.md`.

Полная спецификация со всеми полями — `references/format.md` в репозитории
https://github.com/sirponch-hub/aicanholst"""


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def strip_frontmatter(text):
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S).strip()


def demote(text, levels=1):
    """Опускает уровень заголовков вклеенного раздела.

    Блоки кода пропускаются: там `#` — комментарий, а не заголовок.
    Первый H1 файла удаляется — он становится заголовком раздела.
    """
    out, in_code, seen_h1 = [], False, False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        m = re.match(r"^(#{1,5}) (.*)$", line)
        if m and not in_code:
            level, title = len(m.group(1)), m.group(2)
            if level == 1 and not seen_h1:
                seen_h1 = True
                continue                       # заголовок задаёт сборщик
            out.append("#" * (level + levels - 1) + " " + title)
            continue
        out.append(line)
    return "\n".join(out).strip()


def library_source():
    """holst.py с вклеенной метрикой вместо чтения inter_widths.json."""
    src = read("scripts", "holst.py")
    widths = json.loads(read("scripts", "inter_widths.json"))
    slim = {face: {ch: w for ch, w in table.items() if ch in KEEP}
            for face, table in widths.items()}
    blob = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))

    old = re.search(
        r"_WIDTHS_PATH = .*?REGULAR = SEMIBOLD = \{\}\n", src, flags=re.S)
    if not old:
        raise SystemExit("не нашёл блок загрузки метрики в holst.py")
    new = ('_W = json.loads(r"""%s""")\nREGULAR, SEMIBOLD = _W["regular"], _W["semibold"]\n'
           % blob)
    src = src.replace(old.group(0), new)
    return src.replace('    "inter_widths.json")\n', "")


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "dist/SKILL.md"

    skill = read("SKILL.md")
    frontmatter = re.match(r"\A---\n.*?\n---\n", skill, flags=re.S).group(0)

    # Из основного SKILL.md берём только «Как работать»: остальное вклеиваем
    # из references, чтобы не держать два описания одного и того же.
    how = re.search(r"## Как работать\n(.*?)\n---\n", skill + "\n---\n", flags=re.S)

    parts = [
        frontmatter.rstrip(),
        "",
        "# Доски Холст (.holst)",
        "",
        "Создание и чтение файлов онлайн-доски Холст (holst.so). Формат восстановлен",
        "по штатной выгрузке доски и подтверждён экспериментально.",
        "",
        "Это автономная версия: правила и библиотека вклеены в один файл.",
        "Полный проект с валидатором, рендером превью и тестами —",
        "https://github.com/sirponch-hub/aicanholst",
        "",
        "## Как работать",
        "",
        "1. Уточни структуру доски, если она не задана: какие кадры, что внутри,",
        "   нужны ли связи между элементами.",
        "2. Прочитай раздел «Вёрстка» ниже — без него доска выходит нечитаемой.",
        "3. Запиши библиотеку из раздела «Библиотека» в `holst.py` в рабочей папке",
        "   **дословно, без изменений**, напиши скрипт сборки и запусти его.",
        "4. Прогони обе проверки из раздела «Проверка» и отдай `.holst` пользователю.",
        "",
        "Пользователь открывает файл в Холсте через «восстановить доску из файла».",
        "Импортированная доска получает префикс «Восстановлено» — это нормально.",
        "",
        "**Если пользователь прислал свою выгрузку и просит поправить — не пересобирай",
        "доску генератором**, правь `data.json` точечно: иначе пропадут объекты,",
        "которых нет в библиотеке, и его собственные изменения. См. «Правка чужой доски».",
        "",
        "---",
        "",
        "# Вёрстка",
        "",
        demote(strip_frontmatter(read("references", "layout.md"))),
        "",
        "---",
        "",
        FORMAT_BRIEF,
        "",
        "---",
        "",
        "# Правка чужой доски",
        "",
        # В автономной версии валидатор пишется рядом, а не лежит в scripts/.
        demote(strip_frontmatter(read("references", "editing.md")))
        .replace("scripts/validate.py", "validate.py"),
        "",
        "---",
        "",
        "# Проверка",
        "",
        read("tools", "checks.md").strip(),
        "",
        "---",
        "",
        "# Библиотека",
        "",
        "Запиши следующий код в `holst.py` без изменений:",
        "",
        "```python",
        library_source().rstrip(),
        "```",
        "",
        "# Пример сборки",
        "",
        "```python",
        read("examples", "retro.py").split('sys.path.insert')[1]
            .split("\n", 1)[1].strip(),
        "```",
        "",
        "---",
        "",
        "Геометрия текста и метрика Inter взяты из проекта holst-board",
        "Дмитрия Соловьёва (https://github.com/soloveev/holst-board, CC BY-NC-SA 4.0).",
        "Скилл распространяется на тех же условиях: © 2026 Mikhail Podurets,",
        "CC BY-NC-SA 4.0. Проект неофициальный и не связан с ООО «Холст».",
        "",
    ]

    text = "\n".join(parts)
    os.makedirs(os.path.dirname(os.path.join(ROOT, out_path)) or ".", exist_ok=True)
    with open(os.path.join(ROOT, out_path), "w", encoding="utf-8") as fh:
        fh.write(text)
    print("%s — %d КБ, %d строк" % (out_path, len(text.encode()) / 1024,
                                    text.count("\n") + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
