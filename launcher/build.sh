#!/usr/bin/env bash
# Build tvkit Home (an Android TV launcher whose UI is your redesign page) without Gradle.
#
# usage: launcher/build.sh PAGE.html [WALLPAPER.png] [OUT.apk]
#   PAGE.html       the standalone page from skills/redesign/scripts/build.py (tv-redesign.html)
#   WALLPAPER.png   used for the app's banner/icon (default: tv-redesign-wallpaper.png next to PAGE)
#   OUT.apk         default: ~/.tvkit/launcher/tvkit-home.apk
#
# Needs: a JDK (JAVA_HOME) and the Android SDK (ANDROID_HOME) with build-tools and platforms;android-28.
#   macOS:  brew install openjdk@17 && brew install --cask android-commandlinetools
#           sdkmanager "build-tools;34.0.0" "platforms;android-28"
# The signing key is created once in ~/.tvkit/keystore/ and reused, so updates install over the old app.
set -euo pipefail

PAGE=${1:?usage: launcher/build.sh PAGE.html [WALLPAPER.png] [OUT.apk]}
WALL=${2:-"$(dirname "$PAGE")/tv-redesign-wallpaper.png"}
OUT=${3:-"$HOME/.tvkit/launcher/tvkit-home.apk"}
HERE=$(cd "$(dirname "$0")" && pwd)

JAVA_HOME=${JAVA_HOME:-/opt/homebrew/opt/openjdk@17}
ANDROID_HOME=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-/opt/homebrew/share/android-commandlinetools}}
export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"
BT=$(ls -d "$ANDROID_HOME"/build-tools/* 2>/dev/null | sort -V | tail -1)
JAR="$ANDROID_HOME/platforms/android-28/android.jar"
[ -x "$JAVA_HOME/bin/javac" ] || { echo "no JDK at $JAVA_HOME (set JAVA_HOME)" >&2; exit 1; }
[ -n "$BT" ] && [ -x "$BT/aapt2" ] || { echo "no Android build-tools in $ANDROID_HOME (sdkmanager \"build-tools;34.0.0\")" >&2; exit 1; }
[ -f "$JAR" ] || { echo "missing $JAR (sdkmanager \"platforms;android-28\")" >&2; exit 1; }
[ -f "$PAGE" ] || { echo "page not found: $PAGE" >&2; exit 1; }

W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
mkdir -p "$W/res/drawable" "$W/assets" "$W/classes" "$(dirname "$OUT")"
cp "$PAGE" "$W/assets/home.html"

# Banner (320x180, shown in the TV's Apps list) and icon, cut from the wallpaper.
if [ -f "$WALL" ] && command -v sips >/dev/null; then
  sips -z 180 320 "$WALL" --out "$W/res/drawable/banner.png" >/dev/null
  sips -c 1080 1080 "$WALL" --out "$W/sq.png" >/dev/null && sips -z 192 192 "$W/sq.png" --out "$W/res/drawable/icon.png" >/dev/null
elif [ -f "$WALL" ] && command -v magick >/dev/null; then
  magick "$WALL" -resize 320x180! "$W/res/drawable/banner.png"
  magick "$WALL" -gravity center -crop 1080x1080+0+0 -resize 192x192 "$W/res/drawable/icon.png"
else
  echo "no wallpaper image or image tool (sips/magick) for the banner" >&2; exit 1
fi

VERSION=$(date +%Y%m%d%H)
"$BT/aapt2" compile --dir "$W/res" -o "$W/res.zip"
"$BT/aapt2" link -o "$W/unsigned.apk" -I "$JAR" --manifest "$HERE/AndroidManifest.xml" -A "$W/assets" \
  --version-code "$VERSION" --version-name "0.1.$VERSION" "$W/res.zip"
javac -nowarn -source 8 -target 8 -bootclasspath "$JAR" -classpath "$JAR" -d "$W/classes" \
  "$HERE/src/dev/tvkit/home/MainActivity.java" 2>&1 | grep -v -E "^warning|^Note|^[0-9]+ warning" || true
[ -f "$W/classes/dev/tvkit/home/MainActivity.class" ] || { echo "javac failed" >&2; exit 1; }
"$BT/d8" --release --min-api 24 --lib "$JAR" --output "$W" "$W"/classes/dev/tvkit/home/*.class
(cd "$W" && cp unsigned.apk app.apk && zip -q app.apk classes.dex)
"$BT/zipalign" -f -p 4 "$W/app.apk" "$W/aligned.apk"

KS="$HOME/.tvkit/keystore/tvkit-home.jks"
if [ ! -f "$KS" ]; then
  mkdir -p "$(dirname "$KS")"
  keytool -genkeypair -keystore "$KS" -storepass tvkit-home -keypass tvkit-home -alias tvkit \
    -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=tvkit Home" >/dev/null 2>&1
fi
"$BT/apksigner" sign --ks "$KS" --ks-key-alias tvkit --ks-pass pass:tvkit-home --key-pass pass:tvkit-home \
  --out "$OUT" "$W/aligned.apk"
echo "$OUT ($(($(wc -c < "$OUT") / 1024)) KB, version $VERSION)"
