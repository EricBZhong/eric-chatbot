#!/bin/bash
# ============================================
# CHATBOT LAUNCHER
# Just double-click this file to start the app!
# ============================================

# Move to the directory where this script lives
cd "$(dirname "$0")"

# ---- Cleanup on exit ----
cleanup() {
    echo ""
    echo "Shutting down..."
    echo "Goodbye!"
}
trap cleanup EXIT INT TERM

echo ""
echo "=========================================="
echo "  Starting your Chatbot..."
echo "=========================================="
echo ""

# ---- Python 3 (need 3.10+) ----
NEED_PYTHON=false

if ! command -v python3 &> /dev/null; then
    NEED_PYTHON=true
else
    # Check version — need 3.10+ for modern FastAPI
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
        echo "Python $PY_VERSION found but 3.10+ is required."
        NEED_PYTHON=true
    fi
fi

# Check if a newer Python is already installed but not the default
if [ "$NEED_PYTHON" = true ]; then
    for candidate in python3.13 python3.12 python3.11 python3.10; do
        if command -v "$candidate" &> /dev/null; then
            PY_CMD="$candidate"
            NEED_PYTHON=false
            echo "Found $candidate!"
            break
        fi
    done
    # Also check common Homebrew / python.org install paths
    if [ "$NEED_PYTHON" = true ]; then
        for pypath in /Library/Frameworks/Python.framework/Versions/3.1[0-9]/bin/python3 \
                       /opt/homebrew/bin/python3 /usr/local/bin/python3; do
            if [ -x "$pypath" ]; then
                PV=$("$pypath" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
                if [ -n "$PV" ] && [ "$PV" -ge 10 ]; then
                    PY_CMD="$pypath"
                    NEED_PYTHON=false
                    echo "Found Python 3.$PV at $pypath"
                    break
                fi
            fi
        done
    fi
fi

if [ "$NEED_PYTHON" = true ]; then
    echo "Python 3.10+ not found. Installing Python 3.12..."
    echo "(You may be asked for your Mac password)"
    echo ""

    PYTHON_PKG="/tmp/python-installer.pkg"
    curl -fsSL "https://www.python.org/ftp/python/3.12.4/python-3.12.4-macos11.pkg" -o "$PYTHON_PKG"

    if [ -f "$PYTHON_PKG" ]; then
        sudo installer -pkg "$PYTHON_PKG" -target / 2>/dev/null
        rm -f "$PYTHON_PKG"

        export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"

        if command -v python3.12 &> /dev/null; then
            PY_CMD="python3.12"
            echo "Python 3.12 installed!"
        elif command -v python3 &> /dev/null; then
            PY_CMD="python3"
            echo "Python 3 installed!"
        else
            echo ""
            echo "ERROR: Python install may need a terminal restart."
            echo "Close this window, open it again, and double-click start.command."
            echo ""
            echo "Press any key to exit."
            read -n 1
            exit 1
        fi
    else
        echo ""
        echo "ERROR: Could not download Python installer."
        echo "Please install Python 3.12+ manually: https://www.python.org/downloads/"
        echo ""
        echo "Press any key to exit."
        read -n 1
        exit 1
    fi
fi

# Default to python3 if we haven't set a specific command
PY_CMD="${PY_CMD:-python3}"
echo "Using Python: $($PY_CMD --version)"

# ---- Node.js ----
if ! command -v node &> /dev/null; then
    echo "Node.js not found. Installing..."
    echo "(You may be asked for your Mac password)"
    echo ""

    NODE_PKG="/tmp/node-installer.pkg"
    curl -fsSL "https://nodejs.org/dist/v20.15.0/node-v20.15.0.pkg" -o "$NODE_PKG"

    if [ -f "$NODE_PKG" ]; then
        sudo installer -pkg "$NODE_PKG" -target / 2>/dev/null
        rm -f "$NODE_PKG"

        export PATH="/usr/local/bin:$PATH"

        if command -v node &> /dev/null; then
            echo "Node.js installed: $(node --version)"
        else
            echo "Node.js install may need a terminal restart."
            echo "Close this window, open it again, and double-click start.command."
            echo "Press any key to exit."
            read -n 1
            exit 1
        fi
    else
        echo "Could not download Node.js installer."
        echo "Please install Node.js manually: https://nodejs.org"
        echo "Press any key to exit."
        read -n 1
        exit 1
    fi
else
    echo "Node.js found: $(node --version)"
fi

# ---- Claude CLI ----
# Install locally in the project (no sudo needed) and add to PATH
LOCAL_CLAUDE="$(pwd)/node_modules/.bin/claude"

if command -v claude &> /dev/null; then
    echo "Claude CLI found (global)."
elif [ -x "$LOCAL_CLAUDE" ]; then
    export PATH="$(pwd)/node_modules/.bin:$PATH"
    echo "Claude CLI found (local)."
else
    echo "Installing Claude CLI..."
    npm install --save-dev @anthropic-ai/claude-code 2>&1 | tail -3

    if [ -x "$LOCAL_CLAUDE" ]; then
        export PATH="$(pwd)/node_modules/.bin:$PATH"
        echo "Claude CLI installed!"
    else
        # Fallback: try global install with sudo
        echo "Local install failed, trying global install..."
        sudo npm install -g @anthropic-ai/claude-code 2>/dev/null
        if command -v claude &> /dev/null; then
            echo "Claude CLI installed (global)!"
        else
            echo "WARNING: Claude CLI install failed. AI features will not work."
            echo "Try manually: sudo npm install -g @anthropic-ai/claude-code"
        fi
    fi
fi

# ---- Claude Auth ----
# Check if Claude is already authenticated
if claude auth status &>/dev/null; then
    echo "Claude auth ready."
else
    echo "Claude not authenticated. Running 'claude auth login'..."
    claude auth login
    if [ $? -ne 0 ]; then
        echo "WARNING: Claude auth failed. AI features may not work."
        echo "You can try again later with: claude auth login"
    else
        echo "Claude auth ready."
    fi
fi

# ---- Virtual environment & dependencies ----
VENV_DIR="$(pwd)/venv"
echo ""

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment..."
    $PY_CMD -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo ""
        echo "ERROR: Failed to create virtual environment."
        echo "Try installing Python 3.12+ from https://www.python.org/downloads/"
        echo ""
        echo "Press any key to exit."
        read -n 1
        exit 1
    fi
fi

# Activate venv
source "$VENV_DIR/bin/activate"

echo "Installing Python dependencies..."
pip install --quiet --upgrade pip 2>/dev/null
pip install --quiet -r requirements.txt
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to install Python dependencies."
    echo "Try deleting the 'venv' folder and running this script again."
    echo ""
    echo "Press any key to exit."
    read -n 1
    exit 1
fi
echo "Dependencies OK."

# ---- Verify uvicorn is available ----
python -c "import uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: uvicorn not found even after install."
    echo "Try deleting the 'venv' folder and running this script again."
    echo ""
    echo "Press any key to exit."
    read -n 1
    exit 1
fi

# ---- imessage-exporter (bundled) ----
BIN_DIR="$(dirname "$0")/bin"
EXPORTER="$BIN_DIR/imessage-exporter"

if [ ! -f "$EXPORTER" ]; then
    echo "Downloading imessage-exporter..."
    mkdir -p "$BIN_DIR"
    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ]; then
        EXPORTER_URL="https://github.com/ReagentX/imessage-exporter/releases/download/4.0.0/imessage-exporter-aarch64-apple-darwin"
    else
        EXPORTER_URL="https://github.com/ReagentX/imessage-exporter/releases/download/4.0.0/imessage-exporter-x86_64-apple-darwin"
    fi

    curl -fsSL "$EXPORTER_URL" -o "$EXPORTER" 2>/dev/null
    if [ -f "$EXPORTER" ]; then
        chmod +x "$EXPORTER"
        echo "imessage-exporter ready!"
    else
        echo "NOTE: Could not download imessage-exporter."
        echo "You can still manually upload .txt conversation files."
    fi
else
    echo "imessage-exporter found (bundled)."
fi

echo ""
echo "=========================================="
echo "  Starting server on http://localhost:8000"
echo "=========================================="
echo ""
echo "(Keep this window open while using the app)"
echo ""

# Open browser once server is ready
(
    for i in $(seq 1 30); do
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 2>/dev/null | grep -q "200"; then
            open "http://localhost:8000"
            break
        fi
        sleep 1
    done
) &

# Start the server (when this exits, the cleanup trap fires)
python -m uvicorn app:app --host 0.0.0.0 --port 8000
