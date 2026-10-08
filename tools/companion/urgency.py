"""Compact, dated Urgencias snapshots for the private desktop device."""
import datetime,json,pathlib,subprocess,threading,time,unicodedata
from zoneinfo import ZoneInfo
TZ=ZoneInfo('America/Monterrey')

def charts(counts):
    if not isinstance(counts,dict):raise ValueError('No chart')
    entries=[]
    for name,count in counts.items():
        if isinstance(count,bool) or not isinstance(count,int) or count<0:raise ValueError('Invalid staff count')
        label=unicodedata.normalize('NFKD',str(name)).encode('ascii','ignore').decode().upper()
        label=''.join(c for c in label if c.isalnum() or c in ' .-')[:18]
        if count:entries.append((label or 'SIN ASIGNAR',count))
    entries.sort(key=lambda row:(-row[1],row[0]))
    # Bounded screen series; never silently discard the lower-volume groups.
    if len(entries)>24:entries=entries[:23]+[('OTROS',sum(row[1] for row in entries[23:]))]
    return ';'.join(f'{name}|{count}' for name,count in entries)

def fields(data,now):
    today=datetime.datetime.fromtimestamp(now,TZ).date().isoformat()
    if data.get('day')!=today:return {'ux_day':today,'ux_stale':True}
    result={'ux_day':today,'ux_updated':datetime.datetime.fromtimestamp(data['checked'],TZ).strftime('%H:%M'),
            'ux_stale':now-data['checked']>360}
    for target,source in [('ux_total','patients'),('ux_admissions','admissions'),('ux_voluntary','voluntary'),('ux_nursing_delay','delay_nursing'),('ux_ic_delay','delay_ic')]:
        value=data.get(source)
        if value is not None and (isinstance(value,bool) or not isinstance(value,int) or value<0 or value>999999):raise ValueError('Invalid count')
        result[target]=str(value) if value is not None else '--'
    for target,source in [('ux_doctors','doctors'),('ux_nurses','nurses')]:
        result[target]=charts(data[source])
        if sum(data[source].values())>data['patients']:raise ValueError('Staff counts exceed patients')
    return result

class Urgency:
    def __init__(self):self.lock=threading.Lock();self.data={};self.failed=True
    def refresh(self):
        root=pathlib.Path.home()/'Documents/New project/Susi-Qwen'
        try:
            response=subprocess.run([str(root/'.venv/bin/python'),str(pathlib.Path(__file__).with_name('urgency_source.py'))],capture_output=True,text=True,timeout=90)
            value=json.loads(response.stdout.strip().splitlines()[-1])
            if response.returncode or 'error' in value:raise ValueError('Source unavailable')
            fields(value,time.time())
            with self.lock:self.data=value;self.failed=False
        except (OSError,ValueError,IndexError,subprocess.TimeoutExpired):
            with self.lock:self.failed=True
    def payload(self):
        with self.lock:
            result=fields(self.data,time.time());result['ux_stale']=self.failed or result['ux_stale'];return result
    def start(self):
        def run():
            while True:
                started=time.monotonic();self.refresh();time.sleep(max(1,120-(time.monotonic()-started)))
        threading.Thread(target=run,daemon=True,name='companion-urgency').start();return self
