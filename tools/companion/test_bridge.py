import importlib.util
import sys
import pathlib
import tempfile
import unittest
import json
import hashlib
import hmac
sys.path.insert(0,str(pathlib.Path(__file__).parent))
spec = importlib.util.spec_from_file_location('bridge', pathlib.Path(__file__).with_name('bridge.py'))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
class BridgeTests(unittest.TestCase):
    def test_wifi_signature_and_bounded_packet(self):
        key='a'*64
        payload=bridge.payload_for(bridge.demo_card(),demo=True)
        packet=json.loads(bridge.wifi_packet(payload,key,123456))
        expected=hmac.new(key.encode(),packet['body'].encode(),hashlib.sha256).hexdigest()
        self.assertEqual(packet['sig'],expected)
        self.assertEqual(json.loads(packet['body'])['seq'],123456)
        changed=hmac.new(key.encode(),(packet['body']+' ').encode(),hashlib.sha256).hexdigest()
        self.assertNotEqual(packet['sig'],changed)
        self.assertLess(len(bridge.wifi_packet(payload,key,123456)),1536)
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
            p.write_text('{}'); self.assertEqual(bridge.load_cards(p),([],False))
            p.write_text('bad json'); self.assertEqual(bridge.load_cards(p),([],True))
if __name__=='__main__': unittest.main()
