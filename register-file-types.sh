#!/usr/bin/env bash
# ============================================================
#  retro-amp - Dateiverknuepfung registrieren (Linux/macOS)
#
#  Erstellt eine .desktop-Datei und registriert retro-amp
#  als Audio-Player fuer gaengige Formate via xdg-mime.
#
#  Verwendung:
#    chmod +x register-file-types.sh
#    ./register-file-types.sh
# ============================================================

set -e

APP_NAME="retro-amp"
DESKTOP_FILE="$APP_NAME.desktop"

MIME_TYPES=(
    "audio/mpeg"
    "audio/mp4"
    "audio/x-m4a"
    "audio/ogg"
    "audio/opus"
    "audio/flac"
    "audio/wav"
    "audio/x-wav"
    "audio/x-vorbis+ogg"
)

echo
echo "  retro-amp - Dateiverknuepfung / File Association"
echo

# --- retro-amp finden ---
EXE_PATH=""

# 1. Im PATH
if command -v "$APP_NAME" &> /dev/null; then
    EXE_PATH="$(command -v "$APP_NAME")"
fi

# 2. Installiert (~/.local/bin oder /usr/local/bin)
if [ -z "$EXE_PATH" ] && [ -x "$HOME/.local/bin/$APP_NAME" ]; then
    EXE_PATH="$HOME/.local/bin/$APP_NAME"
fi

if [ -z "$EXE_PATH" ] && [ -x "/usr/local/bin/$APP_NAME" ]; then
    EXE_PATH="/usr/local/bin/$APP_NAME"
fi

# 3. Dev-Umgebung (.venv)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -z "$EXE_PATH" ] && [ -x "$SCRIPT_DIR/.venv/bin/$APP_NAME" ]; then
    EXE_PATH="$SCRIPT_DIR/.venv/bin/$APP_NAME"
fi

if [ -z "$EXE_PATH" ]; then
    echo "  [FEHLER] $APP_NAME nicht gefunden!"
    echo ""
    echo "  Gesucht in:"
    echo "    - PATH"
    echo "    - ~/.local/bin/"
    echo "    - /usr/local/bin/"
    echo "    - $SCRIPT_DIR/.venv/bin/"
    echo ""
    echo "  Bitte zuerst installieren (install.sh oder setup.bat)."
    exit 1
fi

echo "  Gefunden: $EXE_PATH"
echo

# --- .desktop-Datei erstellen ---
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

MIME_STRING=$(IFS=';'; echo "${MIME_TYPES[*]}")

cat > "$DESKTOP_DIR/$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=retro-amp
Comment=Terminal music player with retro charm
Exec=$EXE_PATH %f
Terminal=true
Categories=Audio;Music;Player;
MimeType=$MIME_STRING;
Icon=audio-x-generic
NoDisplay=false
EOF

echo "  [OK] Desktop-Datei erstellt: $DESKTOP_DIR/$DESKTOP_FILE"

# --- Desktop-Datenbank aktualisieren ---
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    echo "  [OK] Desktop-Datenbank aktualisiert"
fi

# --- MIME-Typen zuordnen (xdg-mime) ---
if command -v xdg-mime &> /dev/null; then
    echo ""
    echo "  Registriere MIME-Typen:"
    for mime in "${MIME_TYPES[@]}"; do
        xdg-mime default "$DESKTOP_FILE" "$mime" 2>/dev/null || true
        echo "    $mime"
    done
    echo "  [OK] MIME-Typen registriert"
else
    echo ""
    echo "  [HINWEIS] xdg-mime nicht gefunden."
    echo "  Die .desktop-Datei wurde erstellt, aber die Standard-App"
    echo "  muss manuell im Dateimanager gesetzt werden."
fi

# --- Fertig ---
echo ""
echo "  Fertig! retro-amp ist jetzt verfuegbar fuer:"
echo "    MP3, M4A, OGG, Opus, FLAC, WAV"
echo ""
echo "  Zum Entfernen:"
echo "    rm $DESKTOP_DIR/$DESKTOP_FILE"
echo ""
