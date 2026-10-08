"""Public weather and ETH quotes, refreshed off the notification/voice path."""
import json, math, pathlib, ssl, threading, time, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
TZ=ZoneInfo('America/Monterrey')
WEATHER_URL='https://api.open-meteo.com/v1/forecast?latitude=25.6866&longitude=-100.3161&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code&timezone=America%2FMonterrey'

def get_json(url):
    request=urllib.request.Request(url,headers={'User-Agent':'PocketTank-Companion/1.0'})
    # Framework Python on macOS may lack its own CA bundle; use system roots.
    roots='/etc/ssl/cert.pem'
    context=ssl.create_default_context(cafile=roots if pathlib.Path(roots).is_file() else None)
    with urllib.request.urlopen(request,timeout=8,context=context) as response:return json.load(response)

def number(value,lo,hi):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Invalid public data')
    return value

def weather_fields(data):
    c=data['current'];t=number(c['temperature_2m'],-90,70);feel=number(c['apparent_temperature'],-100,90);humidity=number(c['relative_humidity_2m'],0,100)
    code=number(c['weather_code'],0,99)
    description={0:'DESPEJADO',1:'MAYORMENTE DESPEJADO',2:'PARCIALMENTE NUBLADO',3:'NUBLADO',45:'NIEBLA',48:'NIEBLA',51:'LLOVIZNA',53:'LLOVIZNA',55:'LLOVIZNA',56:'LLOVIZNA HELADA',57:'LLOVIZNA HELADA',61:'LLUVIA',63:'LLUVIA',65:'LLUVIA INTENSA',66:'LLUVIA HELADA',67:'LLUVIA HELADA',71:'NIEVE',73:'NIEVE',75:'NIEVE',77:'NIEVE',80:'CHUBASCOS',81:'CHUBASCOS',82:'CHUBASCOS FUERTES',85:'NIEVE',86:'NIEVE',95:'TORMENTA',96:'TORMENTA CON GRANIZO',99:'TORMENTA CON GRANIZO'}.get(code,'CLIMA VARIABLE')
    observed=datetime.fromisoformat(c['time']).replace(tzinfo=TZ)
    return dict(weather_temp=f'{t:.0f} C',weather_desc=description,weather_feels=f'{feel:.0f} C',weather_humidity=f'{humidity:.0f}%',weather_updated=observed.strftime('%m/%d %H:%M')),observed.timestamp()

def price_fields(usd,mxn):
    values=[]
    for response,currency in ((usd,'USD'),(mxn,'MXN')):
        data=response['data']
        if data['base']!='ETH' or data['currency']!=currency:raise ValueError('Wrong currency')
        value=float(data['amount']);number(value,0.000001,1e9);values.append(value)
    return dict(eth_usd=f'${values[0]:,.2f}',eth_mxn=f'${values[1]:,.2f}',eth_updated=datetime.now(TZ).strftime('%m/%d %H:%M'))

class Ambient:
    def __init__(self,fetch=get_json,clock=time.time):
        self.fetch=fetch;self.clock=clock;self.lock=threading.Lock();self.values={};self.success={};self.failed={'weather':True,'eth':True};self.next={'weather':0,'eth':0}
    def refresh(self):
        now=self.clock()
        for kind,interval in (('weather',600),('eth',120)):
            if now<self.next[kind]:continue
            self.next[kind]=now+interval
            try:
                if kind=='weather':fields,stamp=weather_fields(self.fetch(WEATHER_URL))
                else:fields=price_fields(self.fetch('https://api.coinbase.com/v2/prices/ETH-USD/spot'),self.fetch('https://api.coinbase.com/v2/prices/ETH-MXN/spot'));stamp=self.clock()
                with self.lock:self.values.update(fields);self.success[kind]=stamp;self.failed[kind]=False
            except (OSError,ValueError,KeyError,TypeError,OverflowError):
                with self.lock:self.failed[kind]=True
    def payload(self):
        with self.lock:
            result=dict(self.values)
            for kind,ttl in (('weather',1800),('eth',600)):
                result[kind+'_stale']=self.failed[kind] or self.clock()-self.success.get(kind,0)>ttl
            return result
    def start(self):
        def run():
            while True:self.refresh();time.sleep(5)
        threading.Thread(target=run,daemon=True,name='companion-ambient').start()
        return self
