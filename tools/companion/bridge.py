#!/usr/bin/env python3
"""Read Bob's saved cards and mirror them to Pocket Tank over USB. No bot imports."""
import argparse
import json
import math
import pathlib
import time
import unicodedata

DEFAULT_SOURCE = pathlib.Path.home() / 'Library/Application Support/SuSi/nfl_player_tracking.json'
FIELDS = {'name': 32, 'match': 34, 'title': 31, 'clock': 24, 'updated': 20, 'extra': 39}


def display_text(value, limit):
    value = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode()
    return ''.join(c for c in value if 32 <= ord(c) < 127).upper()[:limit]


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
        cards = [row['last_card'] for row in data.values() if isinstance(row, dict) and isinstance(row.get('last_card'), dict)]
        # Bob saves last_card only after a successful Telegram update. Older data
        # is explicitly labelled instead of claiming the current game is live.
        return cards, time.time() - source.stat().st_mtime > 300
    except FileNotFoundError:
        return [], False
    except (OSError, ValueError, AttributeError):
        return [], True


def message(payload):
    return ('monitor ' + json.dumps(payload, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n').encode()


def demo_card():
    return dict(name='JUGADOR DE EJEMPLO', match='VISITA 14 - 10 LOCAL', title='YARDAS RECIBIDAS',
                clock='Q3 08:24', updated='PRUEBA', extra='DATOS FICTICIOS PARA VERIFICACION', state='in', yards=48, average=65)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
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
    import serial
    connection = None
    show_pending = args.show
    started = time.monotonic()
    try:
        while True:
            try:
                if connection is None:
                    connection = serial.Serial()
                    connection.port, connection.baudrate, connection.timeout = args.port, 115200, 0.2
                    # Opening USB must not reset the running fish simulation.
                    connection.dtr = connection.rts = False
                    connection.open()
                    time.sleep(3)
                    connection.reset_input_buffer()
                    show_pending = args.show
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
