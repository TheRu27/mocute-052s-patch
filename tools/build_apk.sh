#!/usr/bin/env bash
# Pack an ISP file into the official S-series updater as MCT_05000001.ISP and re-sign it.
# Usage: tools/build_apk.sh <firmware.ISP> <out.apk>
#
# Signing: KEYSTORE / KEYSTORE_PASS from the environment or from tools/signing.local (not in git).
# Without them a new key is created in build/. Keep using the same key: Android installs an APK
# over the previous one only if the signature matches.
set -euo pipefail

ISP=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
OUT=$(cd "$(dirname "$2")" && pwd)/$(basename "$2")
ROOT=$(cd "$(dirname "$0")/.." && pwd)
BASE_APK=${BASE_APK:-$ROOT/build/MOCUTE-MFi_M59A01.apk}
[ -f "$BASE_APK" ] || { echo "no $BASE_APK: run tools/fetch_firmware.sh first" >&2; exit 1; }

SDK=${ANDROID_HOME:-$HOME/Library/Android/sdk}
BT=$(ls -d "$SDK"/build-tools/* 2>/dev/null | sort -V | tail -1)
[ -x "$BT/apksigner" ] || { echo "Android SDK build-tools not found (set ANDROID_HOME)" >&2; exit 1; }
if [ -z "${JAVA_HOME:-}" ] && command -v brew >/dev/null; then
  JAVA_HOME=$(brew --prefix openjdk@21 2>/dev/null)/libexec/openjdk.jdk/Contents/Home
  export JAVA_HOME
fi

[ -f "$ROOT/tools/signing.local" ] && . "$ROOT/tools/signing.local"
if [ -z "${KEYSTORE:-}" ]; then
  KEYSTORE=$ROOT/build/patch.keystore
  if [ ! -f "$KEYSTORE" ]; then
    mkdir -p "$ROOT/build"
    openssl rand -hex 16 > "$KEYSTORE.pass"
    "$JAVA_HOME/bin/keytool" -genkeypair -keystore "$KEYSTORE" -alias patch -keyalg RSA -keysize 2048 \
      -validity 10000 -dname "CN=mocute-052-patch" \
      -storepass "$(cat "$KEYSTORE.pass")" -keypass "$(cat "$KEYSTORE.pass")" >/dev/null 2>&1
    echo "created signing key $KEYSTORE"
  fi
  KEYSTORE_PASS=$(cat "$KEYSTORE.pass")
fi
case $KEYSTORE in /*) ;; *) KEYSTORE=$ROOT/$KEYSTORE ;; esac

W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
cp "$BASE_APK" "$W/base.apk"
cd "$W"
zip -q -d base.apk 'META-INF/*'
mkdir -p assets && cp "$ISP" assets/MCT_05000001.ISP
zip -q -0 base.apk assets/MCT_05000001.ISP
"$BT/zipalign" -f -p 4 base.apk aligned.apk
"$BT/apksigner" sign --v4-signing-enabled false --ks "$KEYSTORE" --ks-pass "pass:$KEYSTORE_PASS" --key-pass "pass:$KEYSTORE_PASS" \
  --out "$OUT" aligned.apk
"$BT/apksigner" verify "$OUT"
echo "built $OUT"
