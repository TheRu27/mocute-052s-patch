# MOCUTE-052 S: an everyday remote for a Mac

*Русский: [README.md](README.md)*

The MOCUTE-052 was sold as a remote for VR headsets and mobile games. Many people's VR headsets have long been gathering dust, but the remote itself sits well in the hand: a stick, seven buttons, Bluetooth. This firmware patch turns it into a handy everyday remote for a Mac: watching videos from the couch, flipping through slides and, if you want, a mouse and a gamepad.

Works only with the MOCUTE-052 version S, build `052_S23` (Beken chip, ARM968E-S).

- **KEY — video remote.** The stick sends arrow keys (seeking, player volume, scrolling), X is Space, Power is Esc, A/B are volume, Y is Mute. It is a compromise: a set of keys that is equally useful in players, the browser and presentations.
- **Mouse via ≡** in KEY: the stick moves the cursor, the trigger clicks.
- **GAME — a real HID gamepad** on the Mac: analog stick, analog trigger, 9 buttons. Visible in Chrome and emulators.
- **Auto power-off** after 1 hour without button presses instead of 30 minutes.

Interactive diagram of the controller and the changes (Russian and English): [index.html](index.html).

**Prebuilt APKs** are on the [Releases](../../releases) page: install one on an Android phone and flash the controller (see "Flashing and rollback"). They are unofficial builds based on Mocute's firmware and app and will be removed at the rights holder's first request.

The repository itself contains no Mocute firmware or apps. You can build everything yourself: `tools/fetch_firmware.sh` downloads the originals from the Mocute website and the Web Archive and verifies their SHA-256, and the scripts do the rest (see "Building").

> This project is not affiliated with Mocute. Flashing is at your own risk. The patch targets `052_S23` only: the script checks the SHA-256 of the original firmware and the bytes at every patch location.

## Builds

| APK | Purpose |
|---|---|
| `MOCUTE-052S.apk` | **main**: KEY for video, mouse via ≡, gamepad in GAME, 1 hour until power-off |
| `MOCUTE-052S-clicker.apk` | alternative without the mouse and gamepad on the Mac, but with a PowerPoint clicker in XJMTK mode (see below; not yet tested on the controller) |
| `MOCUTE-052S-restore-original.apk` | rollback to the stock `052_S23` |

## Which controller is supported

MOCUTE-052 version S: it shows up in Bluetooth as `MOCUTE-052_S23-…`; in flashing mode the Mocute updater identifies it as `052S` and looks for the file `MCT_05000001.ISP`. Other 052 versions (F, BLE-M45) and other models are not supported.

## Modes and the switch

The mode is selected by a button combination at power-on and is remembered; a normal power-on with Power keeps the last mode. The KEY/GAME side switch works on the fly. The letters in the combinations are the ones printed on the diamond buttons; Power is the small left button ⏻.

| Power-on | Mode | KEY | GAME (main build) |
|---|---|---|---|
| A+Power | AUTO | video, mouse via ≡ | **HID gamepad** |
| X+Power | NEWGAME | video | not investigated |
| Y+Power | XJMTK | video | stock "arrows + digits" keyboard; in the `clicker` build — clicker |
| B+Power | iCade | video | not tested |
| A+X+Power | flashing | — | — (Bluetooth `MCT-ISP01`) |
| B+Y+Power | reset | — | — |

The main mode for a Mac is **AUTO**.

## What the patch changes

### KEY (all modes)

Report #3 in the HID descriptor is switched from media keys (Consumer) to keyboard keys; the codes are replaced in function `0x59E20`.

| Button | Before | After |
|---|---|---|
| Stick → / ← | next / previous track | → / ← |
| Stick ↑ / ↓ | fast-forward / rewind | ↑ / ↓ |
| X | Play/Pause | Space |
| A / B | volume + / − | keyboard volume + / − |
| Y | Mute | keyboard Mute |
| Power (short press) | "Menu" (on a Mac, after the report type change — F7) | Esc |
| Trigger | Enter | unchanged |

### Mouse and gamepad on the Mac

The controller presents one of two SDP records to the host. The "iOS" record is keyboard only. The "Android" record is mouse, keyboard and gamepad. The firmware decides which one to use based on attributes collected during pairing (judging by the code, the Bluetooth key type), and the Mac gets the "iOS" record. The main build gives the "Android" record to all hosts (the jump at `0x49116`), while keeping the media buttons on the "Apple" branch (`0x59E8C`) so that Y and Power in KEY behave as described above. `--no-android-sdp` disables this change.

Tested on a Mac: the mouse via ≡ in KEY; the gamepad in GAME (AUTO mode) is visible in Chrome. SDL and Steam do not see the controller yet: its primary device type is "mouse", because the mouse is the first collection in the descriptor. The "Game Controllers" section in macOS settings does not show such gamepads at all.

| Button | Gamepad (Chrome) |
|---|---|
| Stick ← / → | axis 0: −1 / +1, analog |
| Stick ↑ / ↓ | axis 1: −1 / +1, analog |
| Trigger | B0 + B9 + axis 4 (analog) |
| Power (short press) | B1 |
| X | B3 |
| Y | B4 |
| B | B7 + mouse click |
| ≡ | B10, short pulse only |
| A | B11 |

The button numbers are set by the firmware for Android: the trigger is A, Power is B, ≡ is Select, the button labeled A is Start.

### Clicker in XJMTK mode (`clicker` build)

XJMTK mode has two stock "gamepad as keyboard" variants for MediaTek-based Android set-top boxes. For Apple hosts, the codes come from the table `0x68E24`, which the patch turns into a clicker. For Android hosts, the codes are hard-coded in function `0x66660` — "arrows + digits". The main build treats the Mac as Android, so the second variant is active there and there is no clicker (A → `1`, X → `3`, stick ↑ → ←). A clicker for the main build is planned.

The clicker in the `clicker` build (table `0x68E24`):

| Button | Before | After | In PowerPoint |
|---|---|---|---|
| Stick → and ↓, X, trigger | `\` `#` Space, `0xC6/0xD0` | → | next slide |
| Stick ← and ↑, A | `;` `'` Backspace | ← | previous slide |
| Y | `-` | F5 | start slideshow |
| B | Esc | `B` | black screen |
| ≡ | `=` | `W` | white screen |
| Power (short press) | `[` | Esc | exit slideshow |
| Stick second layer | numpad | nothing | — |

The trigger was assigned by elimination (table positions 14–15). The `clicker` build itself has not yet been tested on the controller.

### Auto power-off

The threshold in `0x5A3A0` is a single instruction at `0x5A3BC`: 1800 → 3600 seconds. The countdown runs from the last press of any button.

## Building

Requires Python 3, `curl`, `unzip`, Android SDK build-tools (`zipalign`, `apksigner`) and Java (e.g. `brew install openjdk@21`).

```bash
tools/fetch_firmware.sh
python3 tools/patch_firmware.py build/MCT_05000001_052_S23.ISP build/MCT_05000001_052S.ISP
tools/build_apk.sh build/MCT_05000001_052S.ISP build/MOCUTE-052S.apk
```

`clicker` build: add `--no-android-sdp` to `patch_firmware.py`. APK for rollback: the same `build_apk.sh` with the original `build/MCT_05000001_052_S23.ISP`.

Signing: on first run, `build_apk.sh` creates a key in `build/`. Keep it: Android installs a new APK over the old one only if the signatures match. You can set your own key with the `KEYSTORE` and `KEYSTORE_PASS` variables or in `tools/signing.local` (not in git).

## Flashing and rollback

1. Uninstall the official Mocute updater from the phone if it is installed: the patched APK has a different signature.
2. Install the APK.
3. Turn off the controller, hold A+X+Power, pair `MCT-ISP01` in the phone's Bluetooth settings, start the update in the app.
4. Flashing resets the mode to AUTO. On the Mac, remove the controller from Bluetooth and pair it again: macOS caches the HID descriptor.

The bootloader with flashing mode resides below `0x40000` and is not overwritten. Rollback: flash `MOCUTE-052S-restore-original.apk`.

## How the firmware is structured

- The `MCT_05000001.ISP` file is 245,760 bytes. The code (raw `0x00000–0x37FFF`) is stored in blocks of 32 data bytes + 2 bytes of CRC-16 (poly `0x8005`, init `0xFFFF`, big-endian); with the CRC removed, it is loaded at address `0x40000`.
- The settings area (raw `0x38000`–end) is stored as is: the keyboard code table, the name `MOCUTE-052_S23`, and 4 bytes of an unknown checksum at the end. The patch does not touch it.
- The updater (`com.sk.update`) reads the model code from the controller and sends the file `assets/MCT_<code>.ISP` over SPP without any checks.
- For analysis: `tools/DumpDecomp.java` is a headless Ghidra script that dumps the decompilation of all functions (image at `0x40000`, `ARM:LE:32:v5t`).

## Ideas for the future

- Clicker in XJMTK for the main build: replace 14 constants in `0x66660`.
- Gamepad as the first collection in the descriptor — so that SDL and Steam see it.
- Button numbers matching the letters on the case (A/B/X/Y) — for retro games without manual configuration.
- ≡ as a toggle for a second key layer, combinations with modifiers (⌘⇧↩) — requires custom code.
- Vendor/Product ID (Device ID SDP record) — for Steam and the standard mapping in Chrome.

## License

Scripts, documentation and `index.html`: [MIT](LICENSE), © 2026 TheRu27. Mocute firmware and apps, including the patched builds in Releases, are not covered by this license and belong to their rights holder.
