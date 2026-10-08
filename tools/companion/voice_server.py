"""Authenticated LAN microphone receiver, reusing Susi's audio pipeline."""
import concurrent.futures,hashlib,hmac,http.server,io,json,os,pathlib,re,socket,subprocess,tempfile,threading,unicodedata,wave
from notifications import emit,DEFAULT_ROOT
MAX_WAV=44+16000*2*12
PORT=19433

def signature(key,request_id,body):
    return hmac.new(key.encode(),b'voice:'+request_id.encode()+b'\n'+body,hashlib.sha256).hexdigest()

def valid_wav(body):
    try:
        with wave.open(io.BytesIO(body),'rb') as w:
            return w.getnchannels()==1 and w.getsampwidth()==2 and w.getframerate()==16000 and 4000<=w.getnframes()<=192000 and len(w.readframes(w.getnframes()))==w.getnframes()*2
    except (wave.Error,EOFError):return False

def screen_text(value,limit=236):
    value=' '.join(str(value or '').split())
    value=unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode()
    return value if len(value)<=limit else value[:limit-3].rsplit(' ',1)[0]+'...'

class VoiceService:
    def __init__(self,key,root=DEFAULT_ROOT,process=None):
        self.key=key;self.root=pathlib.Path(root);self.lock=threading.Lock();self.busy=False
        self.process=process or self.ask;self.executor=concurrent.futures.ThreadPoolExecutor(max_workers=1)
    def ask(self,body,request_id):
        susi=pathlib.Path.home()/'Documents/New project/Susi-Qwen'
        with tempfile.TemporaryDirectory(prefix='susi-esp32-') as directory:
            wav=pathlib.Path(directory)/'question.wav';wav.write_bytes(body);wav.chmod(0o600)
            result=subprocess.run([str(susi/'.venv/bin/python'),str(pathlib.Path(__file__).with_name('ask_susi.py')),str(wav),request_id],capture_output=True,text=True,timeout=430)
            try:return json.loads(result.stdout.strip().splitlines()[-1])
            except (ValueError,IndexError):return {'error':'No pude comunicarme con Susi. Intenta de nuevo.'}
    def accept(self,request_id,sig,body):
        if not re.fullmatch('[0-9a-f]{32}',request_id) or not hmac.compare_digest(signature(self.key,request_id,body),sig):return 401
        if not valid_wav(body):return 400
        with self.lock:
            if any((self.root/folder/f'{request_id}.json').exists() for folder in ('pending','done')):return 200
            if self.busy:return 409
            self.busy=True
        self.executor.submit(self.run,body,request_id)
        return 202
    def run(self,body,request_id):
        try:
            result=self.process(body,request_id)
            answer=result.get('answer') or result.get('error') or 'No obtuve una respuesta de Susi.'
            emit('Respuesta de Susi',screen_text(answer),source='Susi',priority=2,event_id=request_id,root=self.root,voice_reply_id=request_id)
            history=self.root/'voice-replies';history.mkdir(parents=True,exist_ok=True,mode=0o700)
            fd=os.open(history/f'{request_id}.json',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as f:json.dump(result,f,ensure_ascii=False)
        except Exception:
            emit('Voz de Susi','No pude procesar el audio. Revisa Susi y su lector de audios e intenta de nuevo.',source='Susi',priority=2,event_id=request_id,root=self.root,voice_reply_id=request_id)
        finally:
            with self.lock:self.busy=False

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        self.connection.settimeout(10)
        if self.path!='/voice':self.send_error(404);return
        try:length=int(self.headers.get('Content-Length','0'))
        except ValueError:self.send_error(400);return
        if not 44<=length<=MAX_WAV:self.send_error(413);return
        try:body=self.rfile.read(length)
        except (OSError,socket.timeout):return
        if len(body)!=length:self.send_error(400);return
        code=self.server.service.accept(self.headers.get('X-Voice-ID',''),self.headers.get('X-Voice-Signature',''),body)
        self.send_response(code);self.send_header('Content-Length','0');self.end_headers()

def start(key,host='0.0.0.0',port=PORT,root=DEFAULT_ROOT,process=None):
    server=http.server.ThreadingHTTPServer((host,port),Handler);server.daemon_threads=True
    server.service=VoiceService(key,root,process)
    threading.Thread(target=server.serve_forever,daemon=True,name='susi-voice-http').start()
    return server
