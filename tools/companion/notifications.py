"""Small, atomic local outbox shared by Susi and the ESP32 bridge."""
import argparse
import json
import os
import pathlib
import time
import uuid

DEFAULT_ROOT = pathlib.Path.home() / 'Library/Application Support/BobMonitor/notifications'

def emit(title, message, *, source='Susi', priority=1, ttl=3600, event_id=None, root=DEFAULT_ROOT, demo=False, voice_reply_id=None):
    root = pathlib.Path(root)
    (root/'pending').mkdir(parents=True, exist_ok=True, mode=0o700)
    event_id = event_id or uuid.uuid4().hex
    if not isinstance(event_id,str) or len(event_id)!=32 or any(c not in '0123456789abcdef' for c in event_id):
        raise ValueError('Invalid notification id')
    event={'id':event_id,'source':str(source)[:16],'title':str(title)[:60],'message':str(message)[:400],
           'priority':max(0,min(2,int(priority))),'created':time.time(),'expires':time.time()+max(20,min(86400,ttl)), 'demo':bool(demo)}
    if voice_reply_id:event['voice_reply_id']=voice_reply_id
    if (root/'done'/f'{event_id}.json').exists():return event_id
    target=root/'pending'/f'{event_id}.json'
    if target.exists():return event_id
    temp=target.with_suffix('.'+uuid.uuid4().hex+'.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream: json.dump(event,stream,ensure_ascii=False)
    os.replace(temp,target)
    return event_id

class NotificationQueue:
    def __init__(self,root=DEFAULT_ROOT):self.root=pathlib.Path(root);self.current=None
    def finish(self,event_id):
        if not isinstance(event_id,str) or len(event_id)!=32 or any(c not in '0123456789abcdef' for c in event_id):return
        source=self.root/'pending'/f'{event_id}.json'
        if source.exists():
            (self.root/'done').mkdir(parents=True,exist_ok=True,mode=0o700)
            os.replace(source,self.root/'done'/source.name)
        if self.current and self.current['id']==event_id:self.current=None
    def next(self,now=None):
        now=time.time() if now is None else now
        if self.current and self.current['expires']>now and (self.root/'pending'/f"{self.current['id']}.json").exists():return self.current
        self.current=None; candidates=[]
        for path in (self.root/'pending').glob('*.json'):
            try:
                event=json.loads(path.read_text())
                if path.stem!=event['id'] or not isinstance(event.get('message'),str):continue
                if event['expires']<=now:self.finish(event['id']);continue
                candidates.append(event)
            except (OSError,ValueError,KeyError,TypeError):continue
        if candidates:self.current=sorted(candidates,key=lambda e:(-e['priority'],e['created']))[0]
        return self.current

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('title');p.add_argument('message');p.add_argument('--source',default='Susi');p.add_argument('--demo',action='store_true');p.add_argument('--priority',type=int,default=1);a=p.parse_args()
    emit(a.title,a.message,source=a.source,demo=a.demo,priority=a.priority)
    print('Aviso agregado a la bandeja local del monitor')
