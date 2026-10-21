#!/usr/bin/env bash
# Run ON the Contabo VPS (root). Creates a forward-only user `zbtunnel` that the
# owner's ZBook uses for a reverse SSH tunnel (ZBook:22 -> VPS:2222).
# Agent S then reaches the ZBook via:  ssh -J basira -p 2222 <user>@localhost
set -euo pipefail
U=zbtunnel
id "$U" >/dev/null 2>&1 || useradd -m -s /usr/sbin/nologin "$U"
install -d -m 700 -o "$U" -g "$U" /home/$U/.ssh
KEY=/root/zbook/zbtunnel_key
mkdir -p /root/zbook
[ -f "$KEY" ] || ssh-keygen -t ed25519 -N "" -C "zbook-tunnel" -f "$KEY" >/dev/null
# forwarding only: no shell, no pty, only remote-forward of 127.0.0.1:2222
printf 'restrict,port-forwarding,permitlisten="127.0.0.1:2222" %s\n' "$(cat $KEY.pub)" \
  > /home/$U/.ssh/authorized_keys
chown "$U:$U" /home/$U/.ssh/authorized_keys; chmod 600 /home/$U/.ssh/authorized_keys
# sshd: allow tcp forwarding for this user, keep tunnel alive
if ! grep -q "Match User $U" /etc/ssh/sshd_config; then
cat >> /etc/ssh/sshd_config <<CFG

Match User $U
    AllowTcpForwarding remote
    X11Forwarding no
    AllowAgentForwarding no
    PermitTTY no
    ClientAliveInterval 30
    ClientAliveCountMax 3
CFG
  sshd -t && systemctl reload ssh
fi
# key agent S uses to log into the ZBook (kept on VPS so it survives sandbox death)
SK=/root/zbook/agentS_zbook
[ -f "$SK" ] || ssh-keygen -t ed25519 -N "" -C "agentS->zbook" -f "$SK" >/dev/null
echo "== tunnel user ready. Owner private key: $KEY"; echo "== agent S pubkey for ZBook authorized_keys:"; cat $SK.pub
