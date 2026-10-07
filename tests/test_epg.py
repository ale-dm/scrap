import pathlib
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import cableworld_epg as e  # noqa: E402

HTML = (pathlib.Path(__file__).parent / "fixture.html").read_text(encoding="utf-8")


class EpgTests(unittest.TestCase):
    def test_parse_orders_and_crosses_midnight(self):
        items = e.parse_schedule(HTML)
        self.assertEqual(len(items), 5)
        self.assertEqual(items[0][1], "EMBAJADA AL RA' IS")  # ordenado por hora
        self.assertEqual(items[-2][0].day, 8)  # 00:39 pertenece al día 8
        self.assertEqual(items[2][1], "CHARLA COLOQUIO & ALZHEIMER")

    def test_xmltv_valid_and_contiguous(self):
        items = e.parse_schedule(HTML)
        root = ET.fromstring(e.build_xmltv(items, "CW.es", "Cableworld", 60))
        progs = root.findall("programme")
        self.assertEqual(len(progs), 5)
        for a, b in zip(progs, progs[1:]):
            self.assertEqual(a.get("stop"), b.get("start"))
        self.assertTrue(progs[0].get("start").endswith("+0200"))  # CEST
        self.assertEqual(progs[0].get("channel"), "CW.es")

    def test_empty_page_detected(self):
        self.assertEqual(e.parse_schedule("<html></html>"), [])


if __name__ == "__main__":
    unittest.main()
