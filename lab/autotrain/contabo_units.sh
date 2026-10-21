#!/usr/bin/env bash
# Run ON Contabo as root: installs two always-on systemd services for the training loops.
set -e
R=/opt/almaham/almaham-3
for role in locator reader; do
cat > /etc/systemd/system/almaham-autotrain-$role.service <<UNIT
[Unit]
Description=almaham autotrain loop ($role)
After=network-online.target
[Service]
Type=simple
WorkingDirectory=$R
Environment=ROLE=$role
Environment=OMP_NUM_THREADS=1
ExecStart=/bin/bash $R/lab/autotrain/train_loop.sh
Restart=always
RestartSec=60
[Install]
WantedBy=multi-user.target
UNIT
done
systemctl daemon-reload; systemctl enable --now almaham-autotrain-locator almaham-autotrain-reader
systemctl --no-pager status almaham-autotrain-locator almaham-autotrain-reader | grep -E "Active|autotrain"
