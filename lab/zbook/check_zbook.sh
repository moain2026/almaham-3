#!/usr/bin/env bash
# Agent S side: is the ZBook tunnel up?  (needs ~/.ssh/config Host zbook -> ProxyJump basira, port 2222)
ssh -o ConnectTimeout=8 -o BatchMode=yes zbook 'echo "ZBOOK UP: $(hostname) $(nproc) cores"; free -h | sed -n 2p; python3 --version; nvidia-smi -L 2>/dev/null || echo "no NVIDIA GPU"' 2>&1 | tail -5
