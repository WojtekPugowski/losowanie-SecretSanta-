import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.argv = [sys.argv[0], "--dry-run"]
spec = importlib.util.spec_from_file_location("losowanie", ROOT / "losowanie_whatsapp.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class TestLosowanie(unittest.TestCase):
    def check_bijection(self, a, n):
        self.assertEqual(sorted(a.keys()), list(range(n)))
        self.assertEqual(sorted(a.values()), list(range(n)))
        self.assertTrue(all(k != v for k, v in a.items()), "ktoś wylosował siebie")

    def test_derangement(self):
        for n in range(3, 12):
            for _ in range(300):
                self.check_bijection(m.draw(n, chain=False), n)

    def test_single_chain(self):
        for n in range(3, 12):
            for _ in range(300):
                a = m.draw(n, chain=True)
                self.check_bijection(a, n)
                x, seen = 0, set()
                while x not in seen:
                    seen.add(x)
                    x = a[x]
                self.assertEqual(len(seen), n, "łańcuch rozpadł się na mniejsze cykle")

    def test_phone_normalization(self):
        self.assertEqual(m.normalize_phone("600 100 200"), "48600100200")
        self.assertEqual(m.normalize_phone("+48 601-200-300"), "48601200300")
        self.assertEqual(m.normalize_phone("0049 151 2345678"), "491512345678")
        with self.assertRaises(ValueError):
            m.normalize_phone("123")

    def test_parse_participants(self):
        p = m.parse_participants("Anna, 600100200\nBartek; 601200300\n# komentarz\nCela\t602300400")
        self.assertEqual([x["name"] for x in p], ["Anna", "Bartek", "Cela"])
        with self.assertRaises(ValueError):
            m.parse_participants("Anna, 600100200\nanna, 601200300\nCela, 602300400")
        with self.assertRaises(ValueError):
            m.parse_participants("Anna, 600100200\nBartek, 601200300")

    def test_message_hides_result_after_padding(self):
        msg = m.build_message("Wigilia", "Anna", "Bartek")
        first_lines = "\n".join(msg.splitlines()[:3])
        self.assertNotIn("Bartek", first_lines)
        self.assertIn("*Bartek*", msg.splitlines()[-3])


if __name__ == "__main__":
    unittest.main()
