"""Reuse Susi's existing audio reader and private chat bridge; no Telegram sends."""
import argparse,json,os,pathlib,re,socket,sys
from collections import Counter
from voice_server import prepare_audio,usable_transcript
SUSI=pathlib.Path(os.environ.get('SUSI_PROJECT',str(pathlib.Path.home()/'Documents/New project/Susi-Qwen')))
sys.path.insert(0,str(SUSI))
from dotenv import dotenv_values
from susi_modules.whisper_transcription import transcribe_audio
from susi_core.voice import normalize_spoken_record_request
from web_panel.server import _send_bridge_request,_voice_response_payload

def ask(wav,request_id):
    cfg=dotenv_values(SUSI/'.env.telegram-test')
    if str(cfg.get('SUSI_WHISPER_ENABLED','1')).lower() in {'0','false','no'}:
        raise RuntimeError('La lectura de audios está desactivada en Susi.')
    prepare_audio(wav)
    question=transcribe_audio(wav,base_url=cfg.get('SUSI_WHISPER_BASE_URL') or 'http://127.0.0.1:7860',model=cfg.get('SUSI_WHISPER_MODEL') or 'small',timeout_seconds=180)
    if not usable_transcript(question):
        return {"error":"No entendí bien la pregunta. Habla cerca del micrófono y toca Enviar al terminar."}
    question=normalize_spoken_record_request(question)
    runtime=pathlib.Path(cfg.get('SUSI_RUNTIME_DIR') or 'dev_runtime/telegram-test').expanduser()
    if not runtime.is_absolute():runtime=SUSI/runtime
    response=_send_bridge_request(runtime/'susi-web-bridge.sock',{'request_id':request_id,'text':question,'module':'general','transport':'siri_shortcut'},timeout=240)
    if response.get('error'):raise RuntimeError('Susi no pudo responder a la pregunta.')
    result=_voice_response_payload(response)
    return {'question':question,'answer':result.get('answer') or result.get('spoken_text') or result.get('spoken') or ''}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('wav',type=pathlib.Path);p.add_argument('request_id');args=p.parse_args()
    try:print(json.dumps(ask(args.wav,args.request_id),ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'error':'No pude procesar la voz. Revisa que Susi y su lector de audios estén activos.','type':type(exc).__name__}));sys.exit(1)
