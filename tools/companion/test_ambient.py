import unittest, pathlib,sys,json
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from ambient import Ambient,weather_fields,price_fields
import bridge
class AmbientTests(unittest.TestCase):
    def test_data_and_currencies(self):
        fields,stamp=weather_fields({'current':{'temperature_2m':29,'apparent_temperature':30,'relative_humidity_2m':50,'weather_code':95,'time':'2026-10-08T15:45'}})
        self.assertEqual(fields['weather_desc'],'TORMENTA');self.assertEqual(fields['weather_temp'],'29 C')
        usd={'data':{'base':'ETH','currency':'USD','amount':'2100.23'}};mxn={'data':{'base':'ETH','currency':'MXN','amount':'44900.12'}}
        self.assertEqual(price_fields(usd,mxn)['eth_mxn'],'$44,900.12')
        with self.assertRaises(ValueError):price_fields(mxn,usd)
        usd['data']['amount']='nan'
        with self.assertRaises(ValueError):price_fields(usd,mxn)
    def test_failure_retains_values_and_flags_stale(self):
        a=Ambient(fetch=lambda url:(_ for _ in ()).throw(OSError()),clock=lambda:1000)
        a.values={'eth_usd':'$2,100.00'};a.success={'eth':999};a.failed['eth']=False
        a.refresh();self.assertEqual(a.payload()['eth_usd'],'$2,100.00');self.assertTrue(a.payload()['eth_stale']);self.assertTrue(a.payload()['weather_stale'])
    def test_notification_and_market_packet_fits_receiver(self):
        p=bridge.payload_for({k:'W'*v for k,v in bridge.FIELDS.items()})
        p.update(notice_id='a'*32,notice_source='SUSI',notice_title='T'*32,notice_message='M'*240,notice_time='12:30',voice_reply_id='b'*32)
        p.update(weather_temp='-20 C',weather_desc='TORMENTA CON GRANIZO',weather_feels='-20 C',weather_humidity='100%',weather_updated='10/08 15:45',weather_stale=False,eth_usd='$999,999,999.99',eth_mxn='$999,999,999.99',eth_updated='10/08 15:45',eth_stale=False,local_time='16:00')
        self.assertLess(len(bridge.wifi_packet(p,'a'*64,1234567890123)),2304)
