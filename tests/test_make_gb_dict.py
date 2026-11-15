"""Offline checks for the Gingerbread dictionary writer (no device needed)."""
import gzip, pathlib, subprocess, sys, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import make_gb_dict as m

class DictFormat(unittest.TestCase):
    def build(self, words):
        order, total = m.layout(m.build_trie(words))
        return m.serialize(order, total)

    def test_round_trip_with_spanish_letters(self):
        words = {'de': 225, 'canción': 150, 'canciones': 120, 'mañana': 180, 'pingüino': 70, 'año': 200, 'a': 210}
        data = self.build(words)
        self.assertEqual(dict(m.read_back(data)), words)

    def test_layout_matches_gingerbread_reader(self):
        data = self.build({'ab': 10, 'a': 5})
        # root: 1 child 'a', terminal + has-address flags, 3-byte absolute address, freq.
        self.assertEqual(data[0], 1)
        self.assertEqual(data[1], ord('a'))
        self.assertEqual(data[2] & 0xC0, 0xC0)
        addr = ((data[2] & 0x3F) << 16) | (data[3] << 8) | data[4]
        self.assertEqual(data[5], 5)
        self.assertEqual(addr, 6)
        self.assertEqual(data[addr:], bytes([1, ord('b'), 0x80, 10]))

    def test_root_is_not_misread_as_versioned_header(self):
        data = self.build({'x': 1})
        self.assertFalse(data[0] >= 200 and data[1] in (0, 1))

    def test_cli_on_wordlist(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = pathlib.Path(d) / 'w.combined.gz', pathlib.Path(d) / 'main.dict'
            with gzip.open(src, 'wt', encoding='utf-8') as f:
                f.write('dictionary=main:es,locale=es\n word=hola,f=200,flags=\n word=ñandú,f=90,flags=\n word=adiós,f=150,flags=\n')
            r = subprocess.run([sys.executable, str(ROOT / 'tools/make_gb_dict.py'), str(src), str(out), '--max-words', '2'],
                               capture_output=True, text=True, check=True)
            self.assertIn('round-trip OK', r.stdout)
            self.assertEqual(dict(m.read_back(out.read_bytes())), {'hola': 200, 'adiós': 150})

if __name__ == '__main__':
    unittest.main()
