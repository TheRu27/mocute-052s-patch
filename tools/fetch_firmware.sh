#!/usr/bin/env bash
# Download the vendor files the patch needs into build/ and check their SHA-256.
# They are Mocute's and are not redistributed in this repository.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DIR=$ROOT/build
mkdir -p "$DIR"

sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

fetch() {  # out sha url [url...]
  local out=$1 sha=$2; shift 2
  if [ -f "$out" ] && [ "$(sha256 "$out")" = "$sha" ]; then echo "ok   $(basename "$out")"; return; fi
  for url in "$@"; do
    echo "get  $url"
    if curl -fsSL --retry 2 -o "$out.part" "$url" && [ "$(sha256 "$out.part")" = "$sha" ]; then
      mv "$out.part" "$out"; echo "ok   $(basename "$out")"; return
    fi
    echo "     download failed or SHA-256 mismatch"
  done
  rm -f "$out.part"; echo "could not get $(basename "$out")" >&2; exit 1
}

# Official updater for S-series pads (still served by Mocute); used as the APK shell.
fetch "$DIR/MOCUTE-MFi_M59A01.apk" 4e8e33fc99d7932d1dcd5fec063b542bd9a50d850d4aa7e53ab4a4760a1aa7ce \
  https://www.migamepad.com/sweb/app/tools/MOCUTE-MFi_M59A01.apk \
  https://web.archive.org/web/20240117091245id_/http://www.migamepad.com/sweb/app/tools/MOCUTE-MFi_M59A01.apk

# Old updater (2018) that still contains the 052 S firmware; the current one does not.
fetch "$DIR/mocuteupen.apk" 3dd57e79e5c6bc717c6c3097dbd8b7a3df1f3d9b5ab570303f6f4f83c51e959f \
  https://web.archive.org/web/20180605062743id_/http://www.migamepad.com:80/app/mocute_tool/mocuteupen.apk

unzip -p "$DIR/mocuteupen.apk" assets/MCT_05000001.ISP > "$DIR/MCT_05000001_052_S23.ISP"
[ "$(sha256 "$DIR/MCT_05000001_052_S23.ISP")" = c6117ecb70b7c8b8f6fbe7ff630c156a3135b4a9d59c89a48614d507bda75795 ] \
  || { echo "unexpected MCT_05000001.ISP inside mocuteupen.apk" >&2; exit 1; }
echo "ok   MCT_05000001_052_S23.ISP (original 052_S23 firmware)"
