#!/usr/bin/env bash
# Run ON the owner's HP ZBook (Ubuntu / WSL2-Ubuntu), once:  bash bootstrap_zbook.sh
# 1) installs ssh server + autossh + python; 2) creates limited user `almaham` that agent S logs into;
# 3) opens a persistent reverse tunnel ZBook:22 -> VPS 127.0.0.1:2222 (forward-only key, no shell on VPS).
set -euo pipefail
VPS=80.241.221.190
AGENT_PUB='__AGENT_PUB__'
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openssh-server autossh python3 python3-venv python3-pip git build-essential libgl1 >/dev/null
# limited user for agent S (no password; key only; sudo only for apt-get)
id almaham >/dev/null 2>&1 || sudo useradd -m -s /bin/bash almaham
sudo install -d -m 700 -o almaham -g almaham /home/almaham/.ssh
echo "$AGENT_PUB" | sudo tee /home/almaham/.ssh/authorized_keys >/dev/null
sudo chown almaham:almaham /home/almaham/.ssh/authorized_keys; sudo chmod 600 /home/almaham/.ssh/authorized_keys
echo 'almaham ALL=(ALL) NOPASSWD: /usr/bin/apt-get' | sudo tee /etc/sudoers.d/almaham >/dev/null; sudo chmod 440 /etc/sudoers.d/almaham
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo service ssh restart 2>/dev/null || sudo systemctl restart ssh
# tunnel key (forward-only on the VPS)
mkdir -p ~/.ssh; chmod 700 ~/.ssh
cat > ~/.ssh/zbtunnel_key <<'KEY'
__TUNNEL_KEY__
KEY
chmod 600 ~/.ssh/zbtunnel_key
# tunnel runner (restarts itself)
cat > ~/zbook_tunnel.sh <<'RUN'
#!/usr/bin/env bash
exec autossh -M 0 -N -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
  -o StrictHostKeyChecking=accept-new -i ~/.ssh/zbtunnel_key \
  -R 127.0.0.1:2222:localhost:22 zbtunnel@80.241.221.190
RUN
chmod +x ~/zbook_tunnel.sh
pkill -f 'zbtunnel@' 2>/dev/null || true
nohup ~/zbook_tunnel.sh >~/zbook_tunnel.log 2>&1 &
sleep 4
echo "=== CPU/RAM ==="; nproc; free -h | head -2; python3 --version
echo "=== tunnel ==="; pgrep -fa autossh | head -1 || echo "tunnel NOT running — see ~/zbook_tunnel.log"
echo "DONE. Tell agent S: 'tunnel up'. (WSL: keep this window open, or run  ~/zbook_tunnel.sh  again after reboot)"
