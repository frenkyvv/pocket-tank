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
