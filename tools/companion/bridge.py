#!/usr/bin/env python3
"""Read Bob's saved cards and mirror them to Pocket Tank over USB. No bot imports."""
import argparse
import socket
import hmac
import hashlib
import subprocess
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from notifications import NotificationQueue
import json
import math
import pathlib
import time
import unicodedata

DEFAULT_SOURCE = pathlib.Path.home() / 'Library/Application Support/SuSi/nfl_player_tracking.json'
FIELDS = {'name': 32, 'match': 34, 'title': 31, 'clock': 24, 'updated': 20, 'extra': 39}


def display_text(value, limit):
    value = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode()
    return ''.join(c for c in value if 32 <= ord(c) < 127).replace('\\','/').replace(chr(34),chr(39)).upper()[:limit]


def payload_for(card, stale=False, demo=False):
    payload = {key: display_text(card.get(key), limit) for key, limit in FIELDS.items()}
    payload.update(active=bool(card), demo=demo, stale=stale, state=card.get('state', 'pre'))
    for key in ('yards', 'average'):
        value = card.get(key)
        payload[key] = value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None
    return payload


def load_cards(source):
    try:
        data = json.loads(source.read_text())
        if not isinstance(data, dict):
            return [], True
        cards = [row['last_card'] for row in data.values() if isinstance(row, dict) and isinstance(row.get('last_card'), dict)]
        # Bob saves last_card only after a successful Telegram update. Older data
        # is explicitly labelled instead of claiming the current game is live.
        return cards, bool(cards) and time.time() - source.stat().st_mtime > 300
    except FileNotFoundError:
        return [], False
    except (OSError, ValueError, AttributeError):
        return [], True


def message(payload):
    return ('monitor ' + json.dumps(payload, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n').encode()


def demo_card():
    return dict(name='JUGADOR DE EJEMPLO', match='VISITA 14 - 10 LOCAL', title='YARDAS RECIBIDAS',
                clock='Q3 08:24', updated='PRUEBA', extra='DATOS FICTICIOS PARA VERIFICACION', state='in', yards=48, average=65)



DEFAULT_KEY = pathlib.Path.home() / 'Library/Application Support/BobMonitor/monitor-key'

def wifi_packet(payload, key, seq):
    body = json.dumps(dict(payload, seq=seq), separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    signature = hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return json.dumps({'body': body, 'sig': signature}, separators=(',', ':')).encode()

def broadcast_address():
    try:
        route = subprocess.check_output(['/sbin/route', '-n', 'get', 'default'], text=True)
        interface = re.search(r'interface:\s+(\w+)', route).group(1)
        config = subprocess.check_output(['/sbin/ifconfig', interface], text=True)
        return re.search(r'broadcast\s+([0-9.]+)', config).group(1)
    except (OSError, subprocess.CalledProcessError, AttributeError):
        return '255.255.255.255'

def wifi_main(args):
    key = args.key_file.read_text().strip()
    if len(key) != 64 or any(c not in '0123456789abcdefABCDEF' for c in key):
        raise ValueError('Clave del monitor invalida')
    from voice_server import start as start_voice
    try:
        voice_server=start_voice(key); print('Voz de Susi disponible en la red local',flush=True)
    except OSError:
        voice_server=None; print('No se pudo abrir el receptor de voz; avisos disponibles',flush=True)
    started = time.monotonic()
    notifications = NotificationQueue()
    last_ack = 0
    target = args.host or broadcast_address()
    next_discovery = 0
    show_pending = args.show
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(2)
        while True:
            if not args.host and time.monotonic() > next_discovery:
                target = broadcast_address(); next_discovery = time.monotonic() + 30
            cards, stale = load_cards(args.source)
            index = int((time.monotonic()-started)//12) % max(1,len(cards))
            card = demo_card() if args.demo else cards[index] if cards else {}
            payload = payload_for(card,stale,args.demo)
            payload['show'] = show_pending
            payload['voice_ready'] = voice_server is not None
            event=notifications.next()
            if event:
                payload.update(notice_id=event['id'],notice_source=display_text(event['source'],16),
                    notice_title=display_text(event['title'],32),notice_message=display_text(event['message'],240),
                    notice_time=datetime.fromtimestamp(event['created'],ZoneInfo('America/Monterrey')).strftime('%H:%M'),
                    notice_priority=event['priority'],notice_seconds=20,notice_demo=event.get('demo',False),
                    voice_reply_id=event.get('voice_reply_id',''))
            seq = time.time_ns() // 1000000
            sock.sendto(wifi_packet(payload,key,seq),(target,19432))
            accepted = False
            deadline = time.monotonic()+2
            while time.monotonic()<deadline:
                try:
                    ack, peer = sock.recvfrom(256)
                    data = json.loads(ack)
                    if data.get('ok') is True and data.get('seq') == seq:
                        accepted = True
                        if event and data.get('done')==event['id']:notifications.finish(event['id'])
                        if not last_ack: print('Monitor WiFi conectado: '+peer[0],flush=True)
                        last_ack = time.monotonic(); show_pending = False
                        break
                except socket.timeout: break
                except (ValueError,AttributeError): continue
            if args.once:
                if not accepted: raise RuntimeError('La placa no confirmo la tarjeta por WiFi')
                print('Tarjeta WiFi confirmada por la ESP32'); return
            if last_ack and time.monotonic()-last_ack>30:
                print('Esperando reconexion WiFi del monitor',flush=True);last_ack=0
            time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transport', choices=['usb','wifi'], default='usb')
    parser.add_argument('--host', help='Direccion de la placa; sin ella se descubre mediante la red local')
    parser.add_argument('--key-file', type=pathlib.Path, default=DEFAULT_KEY)
    parser.add_argument('--port', default='/dev/cu.usbmodem2401')
    parser.add_argument('--source', type=pathlib.Path, default=DEFAULT_SOURCE)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--json', action='store_true', help='Read-only preview; do not open the serial port')
    args = parser.parse_args()
    if args.json:
        cards, stale = load_cards(args.source)
        print(json.dumps(payload_for(demo_card() if args.demo else cards[0] if cards else {}, stale, args.demo)))
        return
    if args.transport == "wifi":
        try: wifi_main(args)
        except KeyboardInterrupt: pass
        return
    import serial
    connection = None
    show_pending = args.show
    started = time.monotonic()
    confirmed = False
    try:
        while True:
            try:
                if connection is None:
                    connection = serial.Serial()
                    connection.port, connection.baudrate, connection.timeout = args.port, 115200, 0.2
                    # Native USB-JTAG interprets DTR/RTS transitions as reset.
                    # Let macOS keep those lines instead of toggling on open.
                    connection.dsrdtr = True
                    connection.rtscts = True
                    connection.open()
                    time.sleep(3)
                    connection.reset_input_buffer()
                    show_pending = args.show
                    confirmed = False
                cards, stale = load_cards(args.source)
                index = int((time.monotonic()-started)//12) % max(1, len(cards))
                card = demo_card() if args.demo else cards[index] if cards else {}
                connection.write(message(payload_for(card, stale, args.demo)))
                if show_pending:
                    connection.write(b'monitor show\n')
                    show_pending = False
                connection.flush()
                deadline = time.monotonic()+2
                accepted = False
                while time.monotonic() < deadline:
                    line = connection.readline()
                    if b'MONITOR OK card' in line:
                        accepted = True
                        break
                if accepted and not confirmed:
                    print("Monitor USB conectado; leyendo tarjetas de Bob", flush=True)
                    confirmed = True
                if args.once:
                    if not accepted:
                        raise RuntimeError('La placa no confirmo la tarjeta del monitor')
                    print('Tarjeta confirmada por la ESP32')
                    return
                # Drain logs so firmware console output cannot fill host buffers.
                end = time.monotonic()+3
                while time.monotonic() < end:
                    connection.read(4096)
            except (serial.SerialException, OSError) as exc:
                if connection:
                    connection.close()
                connection = None
                if args.once:
                    raise
                print('Esperando conexion USB:', type(exc).__name__, flush=True)
                time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        if connection:
            connection.close()

if __name__ == '__main__':
    main()
