#!/usr/bin/env bash
# ============================================================
#  retro-amp - Installer
#
#  Verwendung / Usage:
#    curl -fsSL https://github.com/michaelblaess/retro-amp/releases/latest/download/install.sh | bash
#
#  Laedt das neueste Release von GitHub herunter und installiert es.
#  Keine Abhaengigkeiten noetig (kein Python, kein Git).
#
#  Downloads the latest release from GitHub and installs it.
#  No dependencies needed (no Python, no Git).
#
#  Installiert nach / Installs to:
#    Linux:  ~/.local/bin/retro-amp
#    macOS:  /usr/local/bin/retro-amp
# ============================================================

set -e

REPO="michaelblaess/retro-amp"
APP_NAME="retro-amp"

echo
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   retro-amp - Installer                      ║"
echo "  ╚══════════════════════════════════════════════╝"
echo

# --- OS und Architektur erkennen ---
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Linux*)  PLATFORM="linux" ;;
    Darwin*) PLATFORM="macos" ;;
    *)
        echo "  [FEHLER] Nicht unterstuetztes OS: $OS"
        echo "  Unterstuetzt: Linux, macOS"
        echo "  Fuer Windows: irm ...install.ps1 | iex"
        exit 1
        ;;
esac

case "$ARCH" in
    x86_64|amd64)    ARCH_SUFFIX="x64" ;;
    aarch64|arm64)   ARCH_SUFFIX="arm64" ;;
    *)
        echo "  [FEHLER] Nicht unterstuetzte Architektur: $ARCH"
        exit 1
        ;;
esac

# Pfade bestimmen
if [ "$PLATFORM" = "macos" ]; then
    INSTALL_DIR="/usr/local/share/$APP_NAME"
    BIN_DIR="/usr/local/bin"
else
    INSTALL_DIR="$HOME/.$APP_NAME"
    BIN_DIR="$HOME/.local/bin"
fi
WRAPPER="$BIN_DIR/$APP_NAME"

ARTIFACT="${APP_NAME}-${PLATFORM}-${ARCH_SUFFIX}"
ARCHIVE="${ARTIFACT}.tar.gz"

echo "  Plattform / Platform: $PLATFORM ($ARCH_SUFFIX)"
echo

# --- curl oder wget pruefen ---
DOWNLOAD_CMD=""
if command -v curl &> /dev/null; then
    DOWNLOAD_CMD="curl"
elif command -v wget &> /dev/null; then
    DOWNLOAD_CMD="wget"
else
    echo "  [FEHLER] Weder curl noch wget gefunden!"
    echo "  Bitte installieren: sudo apt install curl"
    exit 1
fi

# --- Neuestes Release von GitHub ermitteln ---
echo "  Suche neuestes Release..."
API_URL="https://api.github.com/repos/${REPO}/releases/latest"

if [ "$DOWNLOAD_CMD" = "curl" ]; then
    RELEASE_JSON=$(curl -fsSL "$API_URL" 2>/dev/null) || {
        echo "  [FEHLER] Konnte GitHub API nicht erreichen."
        exit 1
    }
else
    RELEASE_JSON=$(wget -qO- "$API_URL" 2>/dev/null) || {
        echo "  [FEHLER] Konnte GitHub API nicht erreichen."
        exit 1
    }
fi

# Download-URL aus JSON extrahieren (ohne jq)
DOWNLOAD_URL=$(echo "$RELEASE_JSON" | grep -o "\"browser_download_url\": *\"[^\"]*${ARCHIVE}\"" | grep -o "https://[^\"]*")

if [ -z "$DOWNLOAD_URL" ]; then
    echo "  [FEHLER] Kein Release fuer ${ARCHIVE} gefunden!"
    echo
    echo "  Verfuegbare Assets:"
    echo "$RELEASE_JSON" | grep -o '"browser_download_url": *"[^"]*"' | sed 's/.*: *"/    /' | sed 's/"//'
    exit 1
fi

VERSION=$(echo "$RELEASE_JSON" | grep -o '"tag_name": *"[^"]*"' | head -1 | sed 's/.*: *"//' | sed 's/"//')
echo "  [OK] Release gefunden: $VERSION"
echo

# --- Download ---
TMPDIR=$(mktemp -d)
TMPFILE="$TMPDIR/$ARCHIVE"

echo "  Lade herunter / Downloading: $ARCHIVE"
if [ "$DOWNLOAD_CMD" = "curl" ]; then
    curl -fSL --progress-bar -o "$TMPFILE" "$DOWNLOAD_URL"
else
    wget --show-progress -qO "$TMPFILE" "$DOWNLOAD_URL"
fi
echo "  [OK] Download abgeschlossen / Download complete"
echo

# --- Entpacken ---
echo "  Entpacke nach / Extracting to: $INSTALL_DIR"

if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR.bak"
    mv "$INSTALL_DIR" "$INSTALL_DIR.bak"
fi

mkdir -p "$INSTALL_DIR"
tar -xzf "$TMPFILE" -C "$INSTALL_DIR" --strip-components=1
rm -rf "$TMPDIR"
rm -rf "$INSTALL_DIR.bak"

echo "  [OK] Entpackt / Extracted"
echo

# --- Wrapper-Script erstellen ---
mkdir -p "$BIN_DIR"

cat > "$WRAPPER" << SCRIPT
#!/usr/bin/env bash
# retro-amp wrapper (automatisch generiert / auto-generated)
exec "$INSTALL_DIR/$APP_NAME" "\$@"
SCRIPT
chmod +x "$WRAPPER"
chmod +x "$INSTALL_DIR/$APP_NAME"
echo "  [OK] Wrapper erstellt / Wrapper created: $WRAPPER"

# --- PATH pruefen ---
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
    echo
    echo "  [HINWEIS] $BIN_DIR ist nicht im PATH."
    echo "  [NOTE]    $BIN_DIR is not in PATH."
    echo
    SHELL_NAME=$(basename "$SHELL" 2>/dev/null || echo "bash")
    case "$SHELL_NAME" in
        zsh)  RC_FILE="~/.zshrc" ;;
        fish) RC_FILE="~/.config/fish/config.fish" ;;
        *)    RC_FILE="~/.bashrc" ;;
    esac
    echo "  Fuege hinzu / Add to $RC_FILE:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# --- Fertig ---
echo
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   Installation abgeschlossen! ($VERSION)"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║                                              ║"
echo "  ║   Starten mit / Start with:                  ║"
echo "  ║     retro-amp                                ║"
echo "  ║     retro-amp /pfad/zur/musik                ║"
echo "  ║                                              ║"
echo "  ║   Deinstallieren / Uninstall:                ║"
echo "  ║     rm -rf $INSTALL_DIR"
echo "  ║     rm $WRAPPER"
echo "  ║                                              ║"
echo "  ╚══════════════════════════════════════════════╝"
echo
