#!/usr/bin/env bash
# ==============================================================================
# Script: install.sh
# Purpose: Installer for Embedded Hardware Bridge (EHB)
# Author: Patrick Isles (https://github.com/patrick-isles)
# License: MIT
# ==============================================================================

set -euo pipefail

echo "================================================================="
echo "   Embedded Hardware Bridge (EHB) - Installation"
echo "================================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

mkdir -p "${BIN_DIR}"
mkdir -p "${SYSTEMD_USER_DIR}"

# 1. Chmod scripts
chmod +x "${SCRIPT_DIR}/bin/ehb-sim"
chmod +x "${SCRIPT_DIR}/bin/ehb-daemon"
chmod +x "${SCRIPT_DIR}/bin/ehb-monitor"

# 2. Symlink binaries to ~/.local/bin
echo "[+] Linking binaries into ${BIN_DIR}..."
ln -sf "${SCRIPT_DIR}/bin/ehb-sim" "${BIN_DIR}/ehb-sim"
ln -sf "${SCRIPT_DIR}/bin/ehb-daemon" "${BIN_DIR}/ehb-daemon"
ln -sf "${SCRIPT_DIR}/bin/ehb-monitor" "${BIN_DIR}/ehb-monitor"

# 3. Setup systemd user service
echo "[+] Installing systemd user service..."
cat <<EOF > "${SYSTEMD_USER_DIR}/embedded-hardware-bridge.service"
[Unit]
Description=Embedded Hardware Bridge - Telemetry Daemon & Prometheus Exporter
Documentation=https://github.com/patrick-isles/embedded-hardware-bridge
After=default.target

[Service]
Type=simple
ExecStart=${SCRIPT_DIR}/bin/ehb-daemon --device /tmp/ehb-virtual-uart --port 9105
Restart=always
RestartSec=3s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

echo "[+] Reloading systemd user daemon..."
systemctl --user daemon-reload || true

echo ""
echo "================================================================="
echo "   Installation Successful!"
echo "   Commands available in PATH (~/.local/bin):"
echo "     - ehb-sim       : Hardware-in-the-Loop UART Simulator"
echo "     - ehb-daemon    : Telemetry Engine & Prometheus Exporter"
echo "     - ehb-monitor   : ASCII Terminal Oscilloscope & Multi-Meter"
echo ""
echo "   Quickstart:"
echo "     Terminal 1: ehb-sim"
echo "     Terminal 2: ehb-daemon"
echo "     Terminal 3: ehb-monitor"
echo "     Metrics:    curl http://localhost:9105/metrics"
echo "================================================================="
