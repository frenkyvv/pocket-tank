# Bob desktop monitor (first version)

Waveshare AMOLED 1.8 V2. USB-powered, 448 × 368 landscape. Tap BOB at the
upper right of the tank to open the panel; PECERA returns to the tank.
The fish simulation and saves continue while the panel is open.

The host bridge reads `~/Library/Application Support/SuSi/nfl_player_tracking.json`
and mirrors Bob's `last_card`. It never imports the bot, sends Telegram
messages, or writes its tracking state. Multiple saved cards rotate every
12 seconds. Bob typically polls ESPN every 120 seconds; USB checks the saved
cards every approximately 5 seconds. Bob only saves a new card when the
statistics or game state changes, so its clock can remain at the previous
saved update. A saved file older than 5 minutes is conservatively marked
DATOS SIN ACTUALIZAR. USB loss is marked after 30 seconds. No active tracker
shows ESPERANDO SEGUIMIENTO. Unknown yardage stays SIN DATO, never zero.

```
python bridge.py --show
python bridge.py --demo --once --show
python bridge.py --once --show
python bridge.py --json
```

Requires Python and pyserial. `--demo` is explicit and always labelled DEMO.
Serial protocol: newline-delimited `monitor <JSON>` (under 1024 bytes),
`monitor show`, `monitor hide`. Firmware replies MONITOR OK card/show/hide.
Strings are ASCII uppercase and bounded, numbers must be finite. Progress
is against the player's season average, not a betting line; the bar clips
at 100% while the displayed percentage can exceed 100%.

This is a locally signed custom build. Its own signing key is private and
untracked; official OTA images use a different key. Use USB to restore the
official app before using the official OTA updater again. Flash only the
app at 0x10000, preserving the partition table, NVS at 0x9000, model and
Wi-Fi credentials. Back up the device before the first custom flash.

## Wi-Fi transport

`python bridge.py --transport wifi --show` uses a signed UDP snapshot on
port 19432. The sender discovers the broadcast address of the Mac's current
default LAN interface every 30 seconds. Only a matching HMAC-SHA256 key and
an increasing millisecond sequence are accepted. The key is a random
64-character hex string in the Mac's Application Support/BobMonitor/monitor-key
(mode 0600) and the board's separate NVS `monitor/key`. It is never logged
or committed. Configure over USB with `monitor key <hex>` and restart with
`monitor restart`. The original Wi-Fi credentials are reused. A FreeRTOS
queue transfers snapshots to the rendering task; UDP never mutates fish.

The default installed Mac service now uses Wi-Fi, not the serial port.
`--transport usb` remains available for recovery. The Mac must stay awake,
Bob must be running and both devices must share the LAN. No cloud service
or internet forwarding is needed. A USB charger supplies power independently
of the Mac. In idle monitor view, ENLACE WIFI ACTIVO confirms recent snapshots.

## Susi notices

Susi-Qwen writes private-owner reminders, completed web reports and Registry
alert summaries to an atomic local outbox. Reports and Registry never include
patient details. The Wi-Fi bridge sends one notice at a time alongside Bob's
card, retains it until the device acknowledges dismissal or the 20-second
display finishes, and skips expired events (default one hour). Repeated
heartbeats do not reset the notice timer. LISTO returns to the underlying
monitor; PECERA returns to the aquarium. This receipt indicates display
completion, not proof that the user read it. Both devices must share the LAN
and the Mac must be awake. USB recovery does not drain the notification outbox.

Run `python3 -m unittest discover -s tools/companion -p 'test_*.py'` and
`sim/fishsim --companion-notice-preview output.ppm` for transport/outbox and
notice expiry, duplicate suppression and touch behavior checks.

## Push-to-talk with Susi

The rectangular Waveshare 1.8 board offers HABLAR CON SUSI inside the companion panel. Tap, speak, then tap ENVIAR; capture stops automatically after
12 seconds. PECERA cancels recording. The existing codec player owns both
I2S channels; speaker cues are paused while the analog ES8311 microphone
records mono 16-bit PCM at 16 kHz into PSRAM. No continuous listening occurs.

The signed UDP sender also advertises voice readiness. The ESP32 learns
the sender IP only from authenticated snapshots, then uploads a bounded WAV
to the Mac on TCP 19433 with a random request ID and HMAC-SHA256 over
`voice:<id>\n` plus the raw WAV bytes. The receiver validates format, length,
signature and duplicate IDs, accepts one request at a time, and removes its
temporary audio after processing. No router forwarding is required.

`ask_susi.py` runs in the configured Susi-Qwen environment, reuses
`susi_modules.whisper_transcription.transcribe_audio`, and sends the recognized
text to Susi's existing private Unix chat bridge using its voice request route.
The collector returns the answer without sending a Telegram message. A
screen-sized response returns through the notification outbox; full replies
are private JSON under BobMonitor/notifications/voice-replies. Whisper in
Pinokio, Susi, the Mac bridge and the Mac itself must remain running.

Voice touch/cancellation check: `sim/fishsim --companion-voice-preview output.ppm`.
Hardware reference: https://files.waveshare.com/wiki/ESP32-S3-Touch-AMOLED-1.8/ESP32-S3-Touch-AMOLED-1.8.pdf
ES8311 microphone reference: https://github.com/espressif/esp-bsp/blob/master/components/es8311/es8311.c


## Weather and ETH

The aquarium has one circular launcher at the lower right. The panel shows
Monterrey time, a tappable temperature card, voice, tracking, notices, and ETH.
Weather detail shows modeled temperature, apparent temperature and humidity
from Open-Meteo (25.6866, -100.3161). ETH detail shows Coinbase spot quotes
for one ETH in USD and MXN. No API keys or trading credentials are required.

Ambient fetches run in a daemon thread on the Mac, leaving UDP notifications
and voice responsive. Weather polls every ten minutes; ETH every two minutes.
Each card carries its source and local data/consultation time. Failed fetches
retain the last valid values with a stale flag; weather older than 30 minutes,
ETH older than ten minutes, or a missing device heartbeat also show stale.
The receiver accepts up to 2303 bytes including a simultaneous notification.
The Mac and its bridge must remain running; the ESP32 receives signed LAN
snapshots and does not independently fetch internet data.

## Urgencias today

The companion panel includes URGENCIAS. It shows today's registered-patient
count and internamientos from the same `build_urgency_summary_data` used by
Susi's reports. Voluntary discharges come from the official Altas source,
using `count_altas_range`. Nursing/attention delays use Registro column R
(`delays_over_three`); IC delays use Interconsultas' own delay duration.
Both require strictly more than three hours; exactly 3:00 is excluded.

A separate daemon worker invokes `urgency_source.py` in Susi's existing Python
environment every 120 seconds. This adapter loads only report access settings,
uses read-only source calls and existing report functions, and outputs only
aggregates plus staff counters. It does not restart Susi, trigger monitor
corrections, write patient records, or send messages. Updates reflect source
changes on the next poll, including changes made by Susi's live monitor.

The display labels the report date and check time. Failed or old scans retain
last known values with stale status; an unavailable independent source is `--`,
not zero. At the Monterrey date rollover yesterday's metrics are cleared.
Charts show patients per registered staff member, so unassigned patients do
not enter staff counts. Six horizontal bars appear per page; Previous/Next
pages cover up to 24 series. Larger lists retain the first 23 and combine
remaining counts into an explicit OTROS bar. Staff labels are shortened for
the device; no patient names or diagnoses are sent by this adapter.
