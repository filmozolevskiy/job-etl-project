#!/bin/bash
# Install Homebrew and Python on macOS
# Run this script in Terminal.app - you will be prompted for your password

set -e

echo "=== Step 1: Install Homebrew ==="
if command -v brew &>/dev/null; then
    echo "Homebrew is already installed."
else
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add Homebrew to PATH for this session
    if [[ $(uname -m) == "arm64" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi

echo ""
echo "=== Step 2: Add Homebrew to PATH (if not already) ==="
BREW_PREFIX=$(brew --prefix)
SHELL_PROFILE="${HOME}/.zprofile"
if ! grep -q 'brew shellenv' "$SHELL_PROFILE" 2>/dev/null; then
    echo "eval \"\$(${BREW_PREFIX}/bin/brew shellenv)\"" >> "$SHELL_PROFILE"
    echo "Added brew to $SHELL_PROFILE"
else
    echo "Brew already in PATH config."
fi
eval "$(${BREW_PREFIX}/bin/brew shellenv)"

echo ""
echo "=== Step 3: Install Python ==="
brew install python

echo ""
echo "=== Done ==="
python3 --version
echo "Python installed at: $(which python3)"
