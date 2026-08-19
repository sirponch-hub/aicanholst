# Правка чужой доски

Если пользователь уже поработал в Холсте и прислал экспорт, **не пересобирай доску
генератором** — правь `data.json` хирургически.

Причины:

- В файле появляются типы объектов, которых нет в библиотеке (например
  `phosphor-icon`). При пересборке они пропадут, при точечной правке уцелеют.
- Пользователь мог поменять тексты, цвета, добавить логотипы. Генератор об этих
  правках не знает.

Порядок: распаковать, найти нужные объекты по `labelText` фрейма и относительным
координатам, удалить или добавить, записать архив заново, перенеся все ассеты как есть.

```python
import json, zipfile

with zipfile.ZipFile("board.holst") as z:
    data = json.loads(z.read("data.json"))
    assets = {i.filename: z.read(i.filename) for i in z.infolist()
              if i.filename != "data.json"}

# ... правки над data["objects"] ...

data["objects"].sort(key=lambda o: o["zIndex"])
with zipfile.ZipFile("board-fixed.holst", "w", zipfile.ZIP_STORED) as z:
    for name, blob in assets.items():
        z.writestr(name, blob)
    z.writestr("data.json", json.dumps(data, ensure_ascii=False))
```

## Полезные приёмы

- Дети фрейма ищутся по `parentId`; координаты у них абсолютные, поэтому при переносе
  кадра сдвигай и детей, и **точки стрелок** (`start.point` / `end.point` хранят
  абсолютные координаты и не следуют за `parentId`).
- Картинка, лежащая на доске вне фреймов, имеет `parentId: null`. Чтобы положить её
  в кадр, достаточно проставить `parentId` и пересчитать `bounds`.
- `zIndex` у новых объектов бери больше максимального в файле, в конце отсортируй
  список по `zIndex`.

## Проверка отредактированного файла

Запускай валидатор с флагом `--edited`:

```bash
python scripts/validate.py board-fixed.holst --edited
```

Без флага он ругнётся на `bounds.width` у `simple-text`: Холст при сохранении
пересчитывает `bounds` по фактической ширине отрисованного текста, и расхождение там —
норма, а не порча. Инвариант `bounds.width == width × textScale` верен только для
свежесгенерированного файла. У стикеров он держится всегда и проверяется в обоих режимах.

## Снять чужой шаблон

Чтобы собрать новую доску в стиле существующей, посчитай по выгрузке гистограммы:
заливки, обводки, шрифты, цвета текста, кегли. Из самых частых значений собирается
набор токенов, который потом подставляется в генератор.

```python
from collections import Counter
from holst import load

data = load("sample.holst")
fills = Counter(o["fillColor"]["color"] for o in data["objects"]
                if o.get("fillColor") and o["fillColor"].get("color"))
fonts = Counter(o.get("fontFamily") for o in data["objects"] if o.get("fontFamily"))
print(fills.most_common(10), fonts.most_common())
```
