import unittest,datetime,time
from urgency import charts,fields,TZ
class UrgencyTests(unittest.TestCase):
    def data(self,now):return dict(day=datetime.datetime.fromtimestamp(now,TZ).date().isoformat(),checked=now,patients=3,admissions=1,voluntary=None,delay_nursing=1,delay_ic=0,doctors={'MEDICO A':2},nurses={'ENFERMERA A':3})
    def test_unknown_is_not_zero_and_day_rollover_clears(self):
        now=time.time();data=self.data(now);p=fields(data,now)
        self.assertEqual(p['ux_voluntary'],'--');self.assertEqual(p['ux_ic_delay'],'0');self.assertFalse(p['ux_stale'])
        p=fields(data,now+86400);self.assertNotIn('ux_total',p);self.assertTrue(p['ux_stale'])
    def test_freshness_and_staff_reconciliation(self):
        now=time.time();data=self.data(now);data['checked']=now-400
        self.assertTrue(fields(data,now)['ux_stale'])
        data['doctors']['MEDICO B']=2
        with self.assertRaises(ValueError):fields(data,now)
    def test_chart_overflow_retains_all_counts(self):
        source={f'PERSONA {i}':i+1 for i in range(30)};p=charts(source)
        self.assertEqual(len(p.split(';')),24);self.assertIn('OTROS|',p)
        self.assertEqual(sum(int(row.split('|')[1]) for row in p.split(';')),sum(source.values()))
    def test_only_over_three_hours_boundary(self):
        from urgency_source import count_over_three_hours
        from types import SimpleNamespace
        values={'2:59':2+59/60,'3:00':3,'3:01':3+1/60,'4:00':4,'PENDIENTE':None}
        rows=[SimpleNamespace(tardanza=v) for v in values]
        self.assertEqual(count_over_three_hours(rows,values.get),2)

    def test_maximum_notification_ambient_urgency_packet_fits(self):
        import bridge
        p=bridge.payload_for({k:'W'*v for k,v in bridge.FIELDS.items()})
        now=time.time();data=self.data(now);data['patients']=999999
        data['doctors']={('M'*16)+str(i):9999 for i in range(24)}
        data['nurses']={('N'*16)+str(i):9999 for i in range(24)}
        p.update(fields(data,now));p.update(notice_message='M'*240,notice_title='T'*32,notice_source='SUSI',notice_id='a'*32,voice_reply_id='b'*32)
        p.update(weather_desc='TORMENTA CON GRANIZO',weather_updated='10/08 16:00',eth_usd='$999,999,999.99',eth_mxn='$999,999,999.99')
        self.assertLess(len(bridge.wifi_packet(p,'a'*64,1234567890123)),6144)
