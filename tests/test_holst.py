#!/usr/bin/env python3
"""Тесты библиотеки: python3 -m unittest discover tests"""

import json
import os
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import holst  # noqa: E402
from holst import (Board, box_h, fit_fs, fit_scale, grid_size, load,  # noqa: E402
                   object_text)
from validate import check  # noqa: E402


class TestContainer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "b.holst")

    def test_archive_is_stored_and_readable(self):
        b = Board("Тест")
        b.slide(0, 0, "Кадр")
        b.save(self.path)

        with zipfile.ZipFile(self.path) as z:
            self.assertIn("data.json", z.namelist())
            for info in z.infolist():
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
            data = json.loads(z.read("data.json"))

        self.assertEqual(data["boardName"], "Тест")
        self.assertEqual(data["version"], 1)
        self.assertEqual(len(data["objects"]), 1)

    def test_load_roundtrip_and_cyrillic(self):
        b = Board("Доска")
        f = b.slide(0, 0, "Кадр")
        b.sticker(200, 200, "Привет\nмир", parent=f)
        b.save(self.path)

        data = load(self.path)
        sticker = [o for o in data["objects"] if o["type"] == "sticker"][0]
        self.assertEqual(object_text(sticker), "Привет\nмир")


class TestGeometry(unittest.TestCase):
    def test_slide_is_16_9(self):
        b = Board()
        f = b.slide(0, 0)
        self.assertEqual(f["bounds"]["width"] / f["bounds"]["height"], 16 / 9)
        self.assertEqual(f["bounds"]["width"], 4800)

    def test_sticker_bounds_match_scale(self):
        b = Board()
        s = b.sticker(0, 0, "x", scale=3)
        self.assertEqual(s["bounds"]["width"], s["width"] * s["textScale"])

    def test_text_bounds_follow_measured_model(self):
        """Холст хранит рамку на полъединицы шире колонки набора,
        а высоту — числом строк по 21 внутренней единице."""
        b = Board()
        t = b.text(0, 0, "короткая строка", scale=5, width=400)
        self.assertEqual(t["bounds"]["width"], (t["width"] + 0.5) * t["textScale"])
        self.assertEqual(t["bounds"]["height"], 1 * 21 * t["textScale"])

    def test_text_height_grows_by_lines(self):
        b = Board()
        one = b.text(0, 0, "строка", scale=6, width_units=3000)
        many = b.text(0, 0, "слово " * 120, scale=6, width_units=3000)
        self.assertGreater(many["bounds"]["height"], one["bounds"]["height"] * 5)
        self.assertEqual(many["bounds"]["height"] % (21 * 6), 0)

    def test_font_family_not_forced(self):
        """Холст набирает доску своим шрифтом; чужой fontFamily её ломает."""
        b = Board()
        self.assertNotIn("fontFamily", b.text(0, 0, "x"))
        self.assertEqual(b.text(0, 0, "x", font="Bangers")["fontFamily"], "Bangers")

    def test_z_index_grows(self):
        b = Board()
        zs = [b.sticker(0, 0).get("zIndex") for _ in range(5)]
        self.assertEqual(zs, sorted(zs))
        self.assertEqual(len(set(zs)), 5)

    def test_children_are_absolute_and_parented(self):
        b = Board()
        f = b.frame(1000, 1000, 800, 600)
        s = b.sticker(1100, 1100, parent=f)
        self.assertEqual(s["parentId"], f["id"])
        self.assertEqual(s["bounds"]["x"], 1100)     # абсолютные, не относительные

    def test_group_rewrites_parents_and_wraps_bounds(self):
        b = Board()
        a = b.sticker(0, 0, scale=1)
        c = b.sticker(500, 300, scale=1)
        g = b.group([a, c])
        self.assertEqual(a["parentId"], g["id"])
        self.assertEqual(g["bounds"]["width"], 500 + 192)
        self.assertTrue(g["ignoreZIndex"])

    def test_empty_grid_fits_its_box(self):
        b = Board()
        f = b.slide(0, 0)
        b.empty_grid(100, 100, 4, 3, 2000, 1000, parent=f)
        stickers = [o for o in b.objects if o["type"] == "sticker"]
        self.assertEqual(len(stickers), 12)
        right = max(o["bounds"]["x"] + o["bounds"]["width"] for o in stickers)
        bottom = max(o["bounds"]["y"] + o["bounds"]["height"] for o in stickers)
        self.assertLessEqual(right, 100 + 2000 + 1)
        self.assertLessEqual(bottom, 100 + 1000 + 1)

    def test_grid_size_never_below_floor(self):
        self.assertEqual(grid_size(20, 20, 100, 100), 60)


class TestTypography(unittest.TestCase):
    def test_fit_scale_shrinks_long_text(self):
        short = fit_scale("Коротко", 4000, 285, 12.0, floor=6.0)
        long = fit_scale("Очень длинный заголовок " * 6, 4000, 285, 12.0, floor=6.0)
        self.assertEqual(short, 12.0)
        self.assertLess(long, short)
        self.assertGreaterEqual(long, 6.0)

    def test_fit_fs_respects_floor(self):
        fs = fit_fs("текст " * 200, 400, 100, 90)      # не влезет ни при каком кегле
        self.assertGreaterEqual(fs, holst.FS_FLOOR)
        self.assertLess(fs, 90)

    def test_fit_scale_respects_floor(self):
        sc = fit_scale("слово " * 200, 4000, 285, 12.0, floor=6.0)
        self.assertGreaterEqual(sc, 6.0)

    def test_fit_fs_keeps_explicit_small_font(self):
        self.assertEqual(fit_fs("x", 400, 100, 30), 30)   # ниже floor, но задан явно

    def test_shape_autofit_reduces_font(self):
        b = Board()
        s = b.shape(0, 0, 400, 120, "Очень длинный текст который не влезает" * 2,
                    font_size=90, grow=False)
        self.assertLess(s["fontSize"], 90)

    def test_box_h_grows_with_text(self):
        one = box_h("Коротко", 2000, 90)
        many = box_h("Слово " * 60, 2000, 90)
        self.assertGreater(many, one * 3)
        self.assertEqual(box_h("", 2000, 90, minimum=190), 190)
        self.assertGreaterEqual(box_h("Коротко", 2000, 90, minimum=190), 190)

    def test_shape_grows_instead_of_clipping(self):
        """При grow=True фигура обязана вместить текст даже на полу кегля."""
        text = "Очень длинная подпись, которая никак не влезает в узкую полосу " * 3
        b = Board()
        s = b.shape(0, 0, 1200, 120, text, font_size=90)
        self.assertGreater(s["bounds"]["height"], 120)
        self.assertGreaterEqual(s["bounds"]["height"],
                                box_h(text, 1200, s["fontSize"]))

    def test_shape_keeps_height_when_grow_disabled(self):
        b = Board()
        s = b.shape(0, 0, 1200, 120, "текст " * 50, font_size=90, grow=False)
        self.assertEqual(s["bounds"]["height"], 120)

    def test_line_height_matches_holst_internals(self):
        """Внутренний кегль 14, высота строки 21 → интерлиньяж ровно 1.5."""
        self.assertEqual(holst.LINE_H, 1.5)
        self.assertEqual(holst.LINE_INTERNAL / holst.FS_INTERNAL, holst.LINE_H)

    def test_inter_metrics_loaded(self):
        self.assertGreater(len(holst.REGULAR), 150)
        self.assertIn("ж", holst.REGULAR)
        self.assertGreater(holst.ems("Ш"), holst.ems("i"))
        self.assertGreater(holst.ems("Привет", bold=True),
                           holst.ems("Привет", bold=False))


class TestAssets(unittest.TestCase):
    def test_missing_image_fails_early(self):
        b = Board()
        with self.assertRaises(FileNotFoundError):
            b.image(0, 0, "нет-такого-файла.png")

    def test_missing_file_fails_early(self):
        b = Board()
        with self.assertRaises(FileNotFoundError):
            b.file(0, 0, "нет-такого.pdf")


class TestMarkdown(unittest.TestCase):
    def _nodes(self, obj):
        return json.loads(obj["jsonState"]["children"])

    def test_bold_italic_and_color(self):
        b = Board()
        t = b.text(0, 0, "обычный **жирный** и *курсив* и {red10|цветной}")
        leaves = self._nodes(t)[0]["children"][0]["children"]
        marks = {l["text"]: l for l in leaves}
        self.assertTrue(marks["жирный"]["bold"])
        self.assertTrue(marks["курсив"]["italic"])
        self.assertEqual(marks["цветной"]["color"], "red10")
        self.assertNotIn("bold", marks["обычный "])

    def test_hex_color_token(self):
        b = Board()
        t = b.text(0, 0, "{0xFF0002|красный}")
        leaf = self._nodes(t)[0]["children"][0]["children"][0]
        self.assertEqual(leaf["color"], 0xFF0002)

    def test_markdown_can_be_disabled(self):
        b = Board()
        t = b.text(0, 0, "звёздочки **остаются**", markdown=False)
        leaf = self._nodes(t)[0]["children"][0]["children"][0]
        self.assertEqual(leaf["text"], "звёздочки **остаются**")

    def test_markup_does_not_count_towards_width(self):
        """Разметка не должна раздувать расчёт переноса."""
        b = Board()
        plain = b.text(0, 0, "жирный текст", scale=6, width_units=3000)
        marked = b.text(0, 0, "**жирный** текст", scale=6, width_units=3000)
        self.assertEqual(plain["bounds"]["height"], marked["bounds"]["height"])

    def test_ordered_list_restarts_numbering(self):
        b = Board()
        t = b.text(0, 0, "первый\nвторой", block="ol-list-item")
        blocks = [n["children"][0] for n in self._nodes(t)]
        self.assertEqual(blocks[0]["counter"], 1)
        self.assertNotIn("counter", blocks[1])
        self.assertEqual(blocks[1]["type"], "ol-list-item")


class TestNewObjects(unittest.TestCase):
    def test_flip_card_has_both_sides(self):
        b = Board()
        c = b.flip_card(0, 0, "вопрос", "ответ", scale=3)
        self.assertEqual(c["bounds"]["width"], 220 * 3)
        self.assertEqual(c["bounds"]["height"], 320 * 3)
        self.assertNotEqual(c["frontDocumentId"], c["backDocumentId"])
        self.assertIn("вопрос", object_text(c))
        self.assertIn("ответ", object_text(c))

    def test_link_height_grows_with_description(self):
        b = Board()
        short = b.link(0, 0, "https://holst.so", "Холст", "коротко", scale=4)
        long = b.link(0, 0, "https://holst.so", "Холст", "о" * 140, scale=4)
        self.assertEqual(short["bounds"]["width"], 300 * 4)
        self.assertEqual(short["bounds"]["height"], 111 * 4)
        self.assertGreater(long["bounds"]["height"], short["bounds"]["height"])


class TestSlideCursor(unittest.TestCase):
    def test_blocks_stack_without_manual_coordinates(self):
        b = Board()
        s = b.page("Кадр")
        t = s.title("Заголовок")
        body = s.body("Текст задания")
        self.assertGreaterEqual(body["bounds"]["y"],
                                t["bounds"]["y"] + t["bounds"]["height"])
        self.assertEqual(t["parentId"], s.frame["id"])

    def test_page_advances_grid_and_new_row(self):
        b = Board()
        a = b.page("A")
        c = b.page("B")
        self.assertGreater(c.x, a.x)
        self.assertEqual(c.y, a.y)
        b.new_row()
        d = b.page("C")
        self.assertEqual(d.x, a.x)
        self.assertGreater(d.y, a.y)

    def test_columns_split_content_width(self):
        b = Board()
        s = b.page("Кадр")
        cols = s.columns(3, gap=60)
        self.assertEqual(len(cols), 3)
        total = sum(w for _, w in cols) + 2 * 60
        self.assertAlmostEqual(total, s.content_w, places=6)
        self.assertAlmostEqual(cols[0][0], s.left, places=6)

    def test_grid_shrinks_to_fit_remaining_space(self):
        """Сетка обязана ужаться, а не вылезти за нижнее поле кадра."""
        b = Board()
        s = b.page("Кадр")
        s.title("Заголовок")
        s.body("Задание в одну строку")
        stickers = s.empty_grid(4, 3)
        lowest = max(o["bounds"]["y"] + o["bounds"]["height"] for o in stickers)
        self.assertLessEqual(lowest, s.bottom + 1)
        self.assertEqual(len(stickers), 12)


class TestReferenceTypes(unittest.TestCase):
    """Типы, сверенные с эталонной выгрузкой input/elements.holst."""

    def test_stamp_is_reaction_stamp(self):
        """Штамп — это reaction-stamp со stampKey, а не stamp с data."""
        b = Board()
        s = b.stamp(0, 0, "heart")
        self.assertEqual(s["type"], "reaction-stamp")
        self.assertEqual(s["stampKey"], "heart")
        self.assertNotIn("data", s)
        self.assertEqual(s["bounds"]["width"], 60)

    def test_stamp_sticks_to_object(self):
        b = Board()
        target = b.sticker(0, 0, "x")
        s = b.stamp(10, 10, "like", on=target, at=(0.25, 0.75))
        self.assertEqual(s["stickyPosition"]["parentId"], target["id"])
        self.assertEqual(s["stickyPosition"]["x"], 0.25)
        self.assertEqual(s["stickyPosition"]["constraints"],
                         {"x": "normalized", "y": "normalized"})

    def test_card_parses_headings(self):
        b = Board()
        c = b.card(0, 0, "# Раз\nтекст\n## Два\n### Три")
        kinds = [n["children"][0]["type"]
                 for n in json.loads(c["jsonState"]["children"])]
        self.assertEqual(kinds, ["heading-one", "paragraph",
                                 "heading-two", "heading-three"])

    def test_task_card_joins_kanban_column(self):
        b = Board()
        kb = b.kanban(0, 0, ["Нужно", "В работе", "Готово"])
        t = b.task_card(0, 0, "задача", kanban=kb, column=1)
        self.assertEqual(t["parentId"], kb["id"])
        self.assertEqual(t["columnId"], kb["columns"][1]["id"])
        self.assertEqual(t["swimlaneId"], kb["swimlanes"][0]["id"])
        self.assertEqual(t["width"], 338)

    def test_free_task_card_has_null_column(self):
        b = Board()
        t = b.task_card(0, 0, "задача")
        self.assertIsNone(t["columnId"])
        self.assertIsNone(t["swimlaneId"])
        self.assertEqual(t["width"], 320)

    def test_task_card_index_grows(self):
        b = Board()
        idx = [b.task_card(0, 0, str(i))["index"] for i in range(3)]
        self.assertEqual(idx, sorted(idx))
        self.assertEqual(len(set(idx)), 3)

    def test_table_builds_cells_with_fractional_index(self):
        b = Board()
        t = b.table(0, 0, [["a", "b"], ["c", "d"]], col_w=240, row_h=60)
        cells = [o for o in b.objects if o["type"] == "table-cell"]
        self.assertEqual(len(cells), 4)
        self.assertEqual(t["bounds"]["width"], 480)
        self.assertEqual(t["bounds"]["height"], 120)
        self.assertEqual(t["column-1"]["index"], holst.TABLE_INDEX)
        self.assertEqual(t["column-2"]["index"], holst.TABLE_INDEX * 2)
        self.assertTrue(all(c["parentId"] == t["id"] for c in cells))
        self.assertEqual([c["position"] for c in cells], [{"x": 0, "y": 0}] * 4)
        self.assertEqual(object_text(cells[3]), "d")

    def test_table_cell_bounds_are_absolute(self):
        b = Board()
        b.table(1000, 2000, [["a", "b"]], col_w=240, row_h=60)
        cells = [o for o in b.objects if o["type"] == "table-cell"]
        self.assertEqual(cells[0]["bounds"]["x"], 1000)
        self.assertEqual(cells[1]["bounds"]["x"], 1240)

    def test_scaled_types_match_reference_sizes(self):
        """Кость и колесо: логический размер * scale = размер из эталона."""
        b = Board()
        self.assertEqual(b.dice(0, 0, scale=0.5)["bounds"]["width"], 120)
        self.assertEqual(b.spinner(0, 0, ["a"], scale=1.5)["bounds"]["width"], 540)
        self.assertEqual(b.icon(0, 0, "check")["bounds"]["width"], 48)
        self.assertEqual(b.sticker_stack(0, 0)["bounds"]["width"], 232)

    def test_mind_map_node_widens_for_text(self):
        b = Board()
        short = b.mind_map_node(0, 0, "1")
        long = b.mind_map_node(0, 0, "длинная подпись узла")
        self.assertEqual(short["bounds"]["width"], 70)
        self.assertGreater(long["bounds"]["width"], 70)

    def test_code_height_grows_by_lines(self):
        b = Board()
        one = b.code(0, 0, "print(1)")
        three = b.code(0, 0, "a\nb\nc")
        self.assertEqual(three["bounds"]["height"], one["bounds"]["height"] * 3)
        self.assertEqual(three["clonedTextValue"], "a\nb\nc")

    def test_file_carries_mime_and_page_size(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "doc.pdf")
        with open(path, "wb") as fh:
            fh.write(b"%PDF-1.4\n")
        b = Board()
        f = b.file(0, 0, path, pages=101)
        self.assertEqual(f["fileType"], "application/pdf")
        self.assertEqual(f["pagesInfo"], {"count": 101, "valid": True})
        self.assertIn("pageSize", f)
        self.assertNotIn("pinnedPage", f)

    def test_spinner_items_get_ids(self):
        b = Board()
        w = b.spinner(0, 0, ["Вариант 1", "Вариант 2"])
        self.assertEqual([i["label"] for i in w["items"]],
                         ["Вариант 1", "Вариант 2"])
        self.assertEqual(len({i["id"] for i in w["items"]}), 2)


class TestLinks(unittest.TestCase):
    def test_link_on_shape_and_text(self):
        b = Board()
        s = b.shape(0, 0, 100, 100, "к материалам", link="https://example.com")
        t = b.text(0, 0, "к материалам", link="https://example.com")
        self.assertEqual(s["linkTo"], "https://example.com")
        self.assertEqual(t["linkTo"], "https://example.com")

    def test_no_link_field_when_not_asked(self):
        b = Board()
        self.assertNotIn("linkTo", b.shape(0, 0, 100, 100, "x"))
        self.assertNotIn("linkTo", b.text(0, 0, "x"))


class TestArrows(unittest.TestCase):
    def test_arrow_between_binds_to_objects(self):
        b = Board()
        a = b.shape(0, 0, 100, 100)
        c = b.shape(500, 0, 100, 100)
        arr = b.arrow_between(a, c)
        self.assertEqual(arr["start"]["objectId"], a["id"])
        self.assertEqual(arr["end"]["objectId"], c["id"])
        self.assertEqual(arr["start"]["relativePoint"], {"x": 1, "y": 0.5})


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _save(self, board):
        path = os.path.join(self.tmp, "b.holst")
        board.save(path)
        return path

    def test_clean_board_passes(self):
        b = Board("Чистая")
        f = b.slide(0, 0, "Кадр")
        b.shape(200, 300, 2000, 400, "Заголовок блока", font_size=120, parent=f)
        errors, _, _, _ = check(self._save(b))
        self.assertEqual(errors, [])

    def test_catches_overflowing_text(self):
        b = Board("Кривая")
        f = b.slide(0, 0, "Кадр")
        b.shape(200, 200, 400, 120, "Длинный текст " * 12, font_size=90,
                autofit=False, grow=False, parent=f)
        errors, _, _, _ = check(self._save(b))
        self.assertTrue(any("НЕ ВЛЕЗАЕТ" in e for e in errors))

    def test_grown_shape_passes_validation(self):
        """Фигура, выращенная под текст, не должна ловить 'НЕ ВЛЕЗАЕТ'."""
        b = Board("Растущая")
        f = b.slide(0, 0, "Кадр")
        b.shape(200, 300, 2000, 120, "Длинная подпись колонки " * 4,
                font_size=90, parent=f)
        errors, _, _, _ = check(self._save(b))
        self.assertEqual([e for e in errors if "НЕ ВЛЕЗАЕТ" in e], [])

    def test_warns_on_duplicate_frame_names(self):
        b = Board("Дубли")
        b.slide(0, 0, "Упражнение")
        b.slide(5220, 0, "Упражнение")
        _, warnings, _, _ = check(self._save(b))
        self.assertTrue(any("ДУБЛЬ ИМЕНИ" in w for w in warnings))

    def test_edited_flag_skips_text_bounds_check(self):
        """Холст пересчитывает bounds у simple-text — это не порча файла."""
        b = Board("Из Холста")
        f = b.slide(0, 0, "Кадр")
        t = b.text(200, 300, "Правленый в Холсте текст", scale=6, parent=f)
        t["bounds"]["width"] = 777.0          # как после сохранения редактором
        path = self._save(b)

        strict, _, _, _ = check(path)
        relaxed, _, _, _ = check(path, edited=True)
        self.assertTrue(any("bounds.width" in e for e in strict))
        self.assertEqual([e for e in relaxed if "bounds.width" in e], [])

    def test_sticker_bounds_checked_even_when_edited(self):
        b = Board("Из Холста")
        f = b.slide(0, 0, "Кадр")
        s = b.sticker(200, 300, "x", scale=3, parent=f)
        s["bounds"]["width"] = 999.0
        errors, _, _, _ = check(self._save(b), edited=True)
        self.assertTrue(any("bounds.width" in e for e in errors))

    def test_catches_object_below_frame(self):
        b = Board("Кривая")
        f = b.slide(0, 0, "Кадр")
        b.text(200, 2650, "Уходит вниз за границу кадра", scale=6, parent=f)
        errors, _, _, _ = check(self._save(b))
        self.assertTrue(any("НИЖЕ КАДРА" in e for e in errors))

    def test_catches_object_past_right_edge(self):
        b = Board("Кривая")
        f = b.slide(0, 0, "Кадр")
        b.sticker(4700, 1000, "вылез", scale=3, parent=f)
        errors, _, _, _ = check(self._save(b))
        self.assertTrue(any("ШИРЕ КАДРА" in e for e in errors))

    def test_warns_on_tiny_font(self):
        b = Board("Мелко")
        f = b.slide(0, 0, "Кадр")
        b.shape(200, 200, 2000, 300, "мелкая подпись", font_size=20,
                autofit=False, parent=f)
        _, warnings, _, _ = check(self._save(b))
        self.assertTrue(any("МЕЛКИЙ КЕГЛЬ" in w for w in warnings))


class TestExample(unittest.TestCase):
    def test_bundled_example_builds_and_validates(self):
        import subprocess
        tmp = tempfile.mkdtemp()
        subprocess.run([sys.executable, os.path.join(ROOT, "examples", "retro.py")],
                       cwd=tmp, check=True, capture_output=True)
        errors, _, n_obj, n_frames = check(os.path.join(tmp, "retro.holst"))
        self.assertEqual(errors, [])
        self.assertEqual(n_frames, 4)       # три команды + сведение
        self.assertGreater(n_obj, 3)


if __name__ == "__main__":
    unittest.main()
