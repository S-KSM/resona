#!/usr/bin/env bash
# Build the NaoBrain (Resona) menu-bar app as a .app bundle.
#
# Usage:  ./build_app.sh [debug|release]   (default: release)
#
# Output: ./NaoBrain.app  next to this script.
# To install: rsync this onto /Applications/NaoBrain.app.
set -euo pipefail

CONFIG="${1:-release}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/NaoBrain.app"
BIN_NAME="NaoBrain"

cd "$ROOT"
echo "[build] swift build -c $CONFIG"
swift build -c "$CONFIG"

BIN_PATH="$ROOT/.build/$CONFIG/$BIN_NAME"
[[ -x "$BIN_PATH" ]] || { echo "binary not found at $BIN_PATH"; exit 1; }

echo "[bundle] $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cp "$BIN_PATH" "$APP/Contents/MacOS/$BIN_NAME"
cp "$ROOT/Info.plist" "$APP/Contents/Info.plist"

# Preserve the existing AppIcon.icns if one was previously bundled in the
# canonical install location; otherwise the bundle ships without an icon
# and macOS will fall back to a generic placeholder.
if [[ -f "/Applications/NaoBrain.app/Contents/Resources/AppIcon.icns" ]]; then
    cp "/Applications/NaoBrain.app/Contents/Resources/AppIcon.icns" \
       "$APP/Contents/Resources/AppIcon.icns"
fi

# Ad-hoc sign so Gatekeeper and TCC don't quarantine the bundle on launch.
codesign --force --deep --sign - "$APP" >/dev/null

echo "[done] built $APP"
echo "       to install: rsync -a --delete $APP/ /Applications/NaoBrain.app/"
