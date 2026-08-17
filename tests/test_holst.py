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
from holst import Board, fit_fs, fit_scale, grid_size, load, object_text  # noqa: E402
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

    def test_bounds_match_text_scale(self):
        b = Board()
        s = b.sticker(0, 0, "x", scale=3)
        self.assertEqual(s["bounds"]["width"], s["width"] * s["textScale"])
        t = b.text(0, 0, "x", scale=5, width=400)
        self.assertEqual(t["bounds"]["width"], t["width"] * t["textScale"])

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
                    font_size=90)
        self.assertLess(s["fontSize"], 90)


class TestAssets(unittest.TestCase):
    def test_missing_image_fails_early(self):
        b = Board()
        with self.assertRaises(FileNotFoundError):
            b.image(0, 0, "нет-такого-файла.png")

    def test_missing_file_fails_early(self):
        b = Board()
        with self.assertRaises(FileNotFoundError):
            b.file(0, 0, "нет-такого.pdf")


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
                autofit=False, parent=f)
        errors, _, _, _ = check(self._save(b))
        self.assertTrue(any("НЕ ВЛЕЗАЕТ" in e for e in errors))

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
        self.assertEqual(n_frames, 3)
        self.assertGreater(n_obj, 3)


if __name__ == "__main__":
    unittest.main()
