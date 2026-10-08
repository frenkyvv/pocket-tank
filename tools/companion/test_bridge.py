import importlib.util
import pathlib
import tempfile
import unittest
import json
spec = importlib.util.spec_from_file_location('bridge', pathlib.Path(__file__).with_name('bridge.py'))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
class BridgeTests(unittest.TestCase):
    def test_unknown_yards_are_not_zero(self):
        p=bridge.payload_for({'name':'José','yards':None,'average':float('nan')})
        self.assertIsNone(p['yards']); self.assertIsNone(p['average']); self.assertEqual(p['name'],'JOSE')
        self.assertLess(len(bridge.message(p)),1024)
    def test_negative_and_over_average_preserved(self):
        self.assertEqual(bridge.payload_for({'yards':-4})['yards'],-4)
        self.assertEqual(bridge.payload_for({'yards':120,'average':60})['yards'],120)
    def test_reads_cards_without_changing_source(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'state.json'; original=json.dumps({'private-chat':{'last_card':{'name':'Player','yards':48}}})
            p.write_text(original); cards,stale=bridge.load_cards(p)
            self.assertEqual(cards[0]['yards'],48); self.assertFalse(stale); self.assertEqual(p.read_text(),original)
    def test_empty_and_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'state.json'
            self.assertEqual(bridge.load_cards(p),([],False))
            p.write_text('bad json'); self.assertEqual(bridge.load_cards(p),([],True))
if __name__=='__main__': unittest.main()
