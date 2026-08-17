# AI can Holst

Скилл для Claude: генерация и чтение файлов онлайн-доски **[Холст](https://holst.so)** (`.holst`).

Попросите Claude собрать доску — он напишет скрипт, соберёт `.holst`, проверит вёрстку
и отдаст файл. Вы открываете его в Холсте через «восстановить доску из файла».

```
Собери доску для ретроспективы на три команды: что мешало, что помогало,
что попробуем — по кадру на команду.
```

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](LICENSE)

*[English below](#english)*

---

## Что внутри

| | |
|---|---|
| `SKILL.md` | Инструкция для модели |
| `scripts/holst.py` | Библиотека сборки `.holst` — только stdlib |
| `scripts/validate.py` | Проверка файла: схема + не вылезает ли текст |
| `scripts/preview.py` | Рендер кадров в PNG, чтобы посмотреть глазами |
| `references/layout.md` | Правила вёрстки: кадр 16:9, кегль, автоподгонка |
| `references/format.md` | Разбор формата `.holst` |
| `examples/retro.py` | Рабочий пример на три кадра |
| `tests/` | Тесты библиотеки и валидатора |

## Установка

**Claude Code / Cowork** — склонировать в папку скиллов:

```bash
git clone https://github.com/sirponch-hub/aicanholst.git ~/.claude/skills/holst-board
```

Для проекта, а не глобально — в `.claude/skills/holst-board` внутри репозитория.
Claude подхватит скилл сам, когда речь зайдёт о `.holst` или досках Холста.

**Как обычная библиотека** — без Claude тоже работает:

```bash
git clone https://github.com/sirponch-hub/aicanholst.git && cd aicanholst
python3 examples/retro.py && python3 scripts/validate.py retro.holst
```

## Быстрый старт

```python
import sys; sys.path.insert(0, "scripts")
from holst import Board, YELLOW, GREEN

b = Board("Планирование")
f = b.slide(0, 0, "Идеи спринта")          # кадр 16:9, 4800×2700

b.text(300, 200, "Идеи спринта", scale=12, width=350, bold=True, parent=f)
b.sticker_grid(300, 800, ["Онбординг", "Поиск", "Экспорт"],
               cols=3, color=YELLOW, scale=4, parent=f)

a = b.shape(300, 2000, 1200, 300, "Проблема", fill=YELLOW, font_size=90, parent=f)
c = b.shape(2000, 2000, 1200, 300, "Решение", fill=GREEN, font_size=90, parent=f)
b.arrow_between(a, c)

b.save("board.holst")
```

Проверить перед отправкой:

```bash
python3 scripts/validate.py board.holst      # схема и вместимость текста
python3 scripts/preview.py board.holst out/  # PNG кадров — посмотреть композицию
```

## Главное правило вёрстки

**Один кадр — один экран — одна задача.** Кадры строго 16:9 (`4800 × 2700`), внутри —
всё для одного шага: заголовок, задание, рабочая область. Три команды делают
упражнение — это три кадра с продублированным заданием, а не один широкий лист.
Кегль считается от высоты кадра: заголовок 6–8%, тело 3%, ничего мельче 2%.

Подробности и ловушки — в [`references/layout.md`](references/layout.md).

## Зависимости

Библиотека и валидатор — чистый stdlib Python 3.8+. Опционально:

- `pillow` — для `image_fit()` (вписать картинку с сохранением пропорций);
- `cairosvg` — для `preview.py` (без него сохраняются `.svg`);
- `pymupdf` — если тянете картинки из PDF-исходников.

## Тесты

```bash
python3 -m unittest discover tests
```

## Статус и ограничения

Формат разобран по штатной выгрузке доски и подтверждён экспериментально:
сгенерированные файлы открываются в Холсте со всеми объектами, связями и
форматированием. Официальной спецификации нет — формат может измениться
без предупреждения.

Не покрыто: таблицы (`table` / `table-cell`) — собираются вручную по образцу из
выгрузки, см. [`references/format.md`](references/format.md).

Проект неофициальный и не связан с ООО «Холст». Как разбирался формат и как это
соотносится с пользовательским соглашением Холста — в [NOTICE.md](NOTICE.md).

## Вклад

Issues и PR приветствуются. Если формат где-то поехал — приложите к issue минимальную
выгрузку из Холста, на которой видно расхождение.

## Лицензия

[CC BY-NC-SA 4.0](LICENSE) — © 2026 Mikhail Podurets.
Пользоваться и дорабатывать можно со ссылкой на автора; производные — на тех же
условиях; коммерческое использование не допускается.

---

<a name="english"></a>

## English

**AI can Holst** is a Claude skill (and standalone Python library) for generating and
reading `.holst` files — board exports for [Holst](https://holst.so), a Russian online
whiteboard positioned as a Miro replacement.

Ask Claude to build a board and it writes the script, generates the `.holst`, validates
the layout and hands you the file. You import it in Holst via "restore board from file".

**Install** into your skills folder:

```bash
git clone https://github.com/sirponch-hub/aicanholst.git ~/.claude/skills/holst-board
```

**Or use it directly:**

```python
import sys; sys.path.insert(0, "scripts")
from holst import Board, YELLOW

b = Board("Sprint planning")
f = b.slide(0, 0, "Ideas")                # 16:9 frame, 4800×2700
b.sticker_grid(300, 800, ["Onboarding", "Search", "Export"],
               cols=3, color=YELLOW, scale=4, parent=f)
b.save("board.holst")
```

Then `python3 scripts/validate.py board.holst` to check the schema and whether any text
overflows its shape or frame, and `python3 scripts/preview.py board.holst out/` to render
frames as PNG.

**Key layout rule:** one frame = one screen = one task. Keep every frame at 16:9
(`4800 × 2700`) and size type as a share of frame height — headings 6–8%, body 3%,
nothing below 2%. Boards built as wide sheets are unreadable in the room.

The documentation, docstrings and skill instructions are in Russian, since Holst is a
Russian product — but the API itself is plain English and usable without it.

The format was reconstructed from Holst's own board export (user content, not the
service's code) and verified experimentally; there is no official spec, so it may change.
See [NOTICE.md](NOTICE.md). Unaffiliated with Holst.

Licensed [CC BY-NC-SA 4.0](LICENSE) — © 2026 Mikhail Podurets. Use and adapt with
attribution, share alike, no commercial use.
