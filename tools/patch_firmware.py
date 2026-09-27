#!/usr/bin/env python3
"""Patch MOCUTE-052 S firmware (MCT_05000001.ISP, build 052_S23) for everyday use with a Mac:
KEY mode sends keyboard keys instead of consumer media keys (arrows, Space, Esc), every host
gets the "Android" HID description (mouse via the menu button in KEY, HID gamepad in GAME),
the XJMTK key table (Y+Power, GAME) becomes a presentation clicker, and idle power-off is
1 h instead of 30 min. --no-android-sdp keeps the stock host detection: no mouse or gamepad
on Apple hosts, but there XJMTK uses the clicker table.

ISP layout: code area (raw 0x00000-0x37FFF) is stored as 32 data bytes + 2 bytes
CRC-16 (poly 0x8005, init 0xFFFF, big-endian); the stripped code runs at 0x40000.
Config area (raw 0x38000-end) is plain and left untouched.

Usage: patch_firmware.py <original.ISP> <out.ISP> [--dump-code code.bin]
"""
import argparse
import hashlib

# SHA-256 of the only firmware this patch was made for: MOCUTE-052 version S, build 052_S23
# (assets/MCT_05000001.ISP from the vendor updater mocuteupen.apk, 2018). tools/fetch_firmware.sh gets it.
ORIGINAL_SHA256 = "c6117ecb70b7c8b8f6fbe7ff630c156a3135b4a9d59c89a48614d507bda75795"

BASE = 0x40000
CONFIG_RAW = 0x38000

# Consumer collection (report ID 3, 2 x 16-bit usages) -> keyboard collection of the
# same length. LogMax 0xFF is inherited from the keyboard collection just before it.
OLD_DESC = bytes.fromhex("050c0901a1018503150026800319002a8003751095028100c0")
NEW_DESC = bytes.fromhex("05010906a1018503050715003500190029ff751095028100c0")
DESC_ADDRS = (0x68EC2, 0x6A1F4)  # two descriptor sets (different power-on modes)

# `movs r1/r6, #imm` operands in the KEY-mode report builder at 0x59E20.
# addr: (consumer usage, keyboard usage)
CODE_PATCHES = {
    0x59E46: (0xCD, 0x2C),  # Play/Pause    -> Space
    0x59E4E: (0xB5, 0x4F),  # Next track    -> Right arrow
    0x59E56: (0xB6, 0x50),  # Prev track    -> Left arrow
    0x59E5E: (0xEA, 0x81),  # Volume down   -> Keyboard Volume Down
    0x59E66: (0xE9, 0x80),  # Volume up     -> Keyboard Volume Up
    0x59E6E: (0xB3, 0x52),  # Fast forward (stick up)   -> Up arrow
    0x59E76: (0xB4, 0x51),  # Rewind (stick down)       -> Down arrow
    0x59E96: (0xE2, 0x7F),  # Mute (Y)                  -> Keyboard Mute
    0x59ECE: (0x40, 0x29),  # Menu (Power, short press) -> Esc (as keyboard usage 0x40 it was F7)
}

# Whole-instruction patches: addr: (old bytes, new bytes).
INSN_PATCHES = {
    # Idle power-off threshold in 0x5A3A0: `movs r1,#0xE1; lsls r1,r1,#3` = 1800 s.
    # lsls #3 -> #4 gives 3600 s (1 h). The idle counter is 16-bit, keep it < 65536.
    0x5A3BC: (bytes.fromhex("c900"), bytes.fromhex("0901")),
}


# Default (off with --no-android-sdp): serve every host the "Android" SDP record, i.e. the
# 234-byte descriptor with mouse + keyboard + report 3 + gamepad instead of the 90-byte
# keyboard-only one that Apple hosts get. Side effect: XJMTK then uses the hard-coded
# "arrows + digits" keys in 0x66660 instead of the clicker table at 0x68E24.
ANDROID_SDP_PATCHES = {
    # 0x49080 picks "ios_setup" vs "andoird_setup": `bge` -> `b`, always Android.
    0x49116: (bytes.fromhex("11da"), bytes.fromhex("11e0")),
    # 0x59E20 media keys: skip the non-Apple branch (Power -> AC Back, Y -> Menu) so KEY
    # keeps Y = Mute and Power = Esc: `beq` -> `mov r8, r8` (Thumb NOP on ARMv5).
    0x59E8C: (bytes.fromhex("0cd0"), bytes.fromhex("c046")),
}

# XJMTK mode (Y+Power), switch in GAME: plain keyboard keys from the table at 0x68E24.
# Turned into a presentation clicker. index: (original usage, new usage)
XJMTK_TABLE = 0x68E24
XJMTK_PATCHES = {
    0: (0x31, 0x4F),   # stick right/down ('\')  -> Right arrow (next slide)
    1: (0x32, 0x4F),   # stick right/down ('#')  -> Right arrow
    2: (0x33, 0x50),   # stick left (';')        -> Left arrow (previous slide)
    3: (0x34, 0x50),   # stick up (''')          -> Left arrow
    4: (0x2A, 0x50),   # A (Backspace)           -> Left arrow
    5: (0x29, 0x05),   # B (Esc)                 -> 'b' (black screen)
    6: (0x2C, 0x4F),   # X (Space)               -> Right arrow
    7: (0x2D, 0x3E),   # Y ('-')                 -> F5 (start slide show)
    10: (0x2E, 0x1A),  # ≡ ('=')                 -> 'w' (white screen)
    11: (0x2F, 0x29),  # Power, short ('[')      -> Esc (end show)
    14: (0xC6, 0x4F),  # trigger (probably)      -> Right arrow
    15: (0xD0, 0x4F),  # trigger (probably)      -> Right arrow
    # Keypad keys the stick sends as a second layer (deflection/diagonals) -> no key
    16: (0x60, 0x00), 17: (0x61, 0x00), 18: (0x55, 0x00), 19: (0x57, 0x00),
    20: (0x56, 0x00), 21: (0x58, 0x00), 22: (0x59, 0x00),
}


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for x in data:
        crc ^= x << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x8005) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def raw_offset(addr: int) -> int:
    off = addr - BASE
    return off // 32 * 34 + off % 32


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--dump-code", help="also write the stripped code image (load at 0x40000)")
    ap.add_argument("--no-android-sdp", action="store_true",
                    help="keep stock host detection: no mouse/gamepad on Apple hosts, "
                         "but the XJMTK clicker table works there")
    ap.add_argument("--any-input", action="store_true",
                    help="skip the SHA-256 check of the input firmware (the byte checks still apply)")
    args = ap.parse_args()

    orig = open(args.src, "rb").read()
    digest = hashlib.sha256(orig).hexdigest()
    if digest != ORIGINAL_SHA256 and not args.any_input:
        raise SystemExit(f"{args.src}: SHA-256 {digest} is not the 052_S23 firmware this patch "
                         "was made for (see tools/fetch_firmware.sh). Use --any-input to force.")
    buf = bytearray(orig)

    def read(addr, n):
        return bytes(buf[raw_offset(addr + i)] for i in range(n))

    def write(addr, data):
        for i, x in enumerate(data):
            buf[raw_offset(addr + i)] = x

    for addr in DESC_ADDRS:
        assert read(addr, len(OLD_DESC)) == OLD_DESC, f"unexpected descriptor at {addr:#x}"
        write(addr, NEW_DESC)
    for addr, (old, new) in CODE_PATCHES.items():
        imm, op = read(addr, 2)
        assert imm == old and op & 0xF8 == 0x20, f"unexpected instruction at {addr:#x}"
        write(addr, [new])
    insn_patches = dict(INSN_PATCHES)
    if not args.no_android_sdp:
        insn_patches.update(ANDROID_SDP_PATCHES)
    for addr, (old, new) in insn_patches.items():
        assert read(addr, len(old)) == old, f"unexpected instruction at {addr:#x}"
        write(addr, new)
    for idx, (old, new) in XJMTK_PATCHES.items():
        assert read(XJMTK_TABLE + idx, 1)[0] == old, f"unexpected XJMTK key #{idx}"
        write(XJMTK_TABLE + idx, [new])

    touched = sorted({i // 34 for i in range(CONFIG_RAW) if buf[i] != orig[i]})
    for blk in touched:
        s = blk * 34
        buf[s + 32 : s + 34] = crc16(bytes(buf[s : s + 32])).to_bytes(2, "big")
    assert buf[CONFIG_RAW:] == orig[CONFIG_RAW:]

    open(args.dst, "wb").write(buf)
    print(f"{args.dst}: {len(touched)} blocks re-CRC'd, "
          f"{sum(a != b for a, b in zip(buf, orig))} bytes changed")

    if args.dump_code:
        code = b"".join(orig[i : i + 32] for i in range(0, CONFIG_RAW, 34))
        open(args.dump_code, "wb").write(code)


if __name__ == "__main__":
    main()
