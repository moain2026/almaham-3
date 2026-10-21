# ZBook (owner's HP ZBook i7/16 GB) as a third training machine — runbook (2026-10-21)

**Design:** the ZBook has no public IP, so it opens a *reverse* SSH tunnel to the Contabo VPS
(`ZBook:22 → VPS 127.0.0.1:2222`). Agent S reaches it with `ssh zbook` (ProxyJump via `basira`).
The VPS user `zbtunnel` is **forward-only** (`restrict,permitlisten=127.0.0.1:2222`, no shell, no PTY),
so the ZBook key cannot do anything on the VPS except hold the tunnel. On the ZBook, agent S logs in
as the limited user `almaham` (key only, sudo only for `apt-get`).

| Where | File | Purpose |
|---|---|---|
| VPS | `lab/zbook/setup_tunnel_vps.sh` (ran once as root) | creates `zbtunnel`, keys in `/root/zbook/`, sshd Match block |
| ZBook | `lab/zbook/bootstrap_zbook.sh` (template; filled copy with keys is **only** on the VPS `/root/zbook/bootstrap_zbook_filled.sh`) | installs ssh/autossh/python, user `almaham`, starts tunnel |
| sandbox | `lab/zbook/check_zbook.sh` + `~/.ssh/config Host zbook` | test connection |
| VPS | webdemo `/meter/dl?f=<file>&t=<token>` (env `DL_DIR`,`DL_TOKEN` in the systemd unit) | one-time private download of the filled bootstrap; returns 404 without token |

## Owner steps
- **Linux (Ubuntu):** open terminal → `curl -fsSL '<dl-url>' -o b.sh && bash b.sh`.
- **Windows:** install WSL2 Ubuntu first (`wsl --install -d Ubuntu` in PowerShell as admin, reboot, set a user), then run the same line inside Ubuntu. Keep the WSL window open (or run `~/zbook_tunnel.sh` after reboot).
- Note the script prints `nproc`, RAM, Python version and whether the tunnel is running.

## Agent S steps after "tunnel up"
1. `bash lab/zbook/check_zbook.sh` → must print `ZBOOK UP`.
2. Clone + venv on the ZBook as `almaham`: `git clone https://github.com/moain2026/almaham-3 -b genspark_ai_developer`, `python3 -m venv .venv && .venv/bin/pip install -r lab/requirements.txt` (CPU torch; ~1.5 GB).
3. Copy shards (`data/erp/ft/*.npy`, ~3 GB) and `lab/weights/*.pt` with `rsync -az -e ssh` **via the VPS** (`scp -3` or rsync from basira), never through the public repo.
4. Train with `TORCH_THREADS=$(nproc)`; copy weights back; evaluate **only** in the sandbox/VPS with `eval_ckpt.sh` + `eval_testset_human.py`; log in `docs/training-log/runs.md`.
5. Private photos never leave `almaham-3-private-data`/VPS except to the ZBook training dir, which is owner-controlled hardware.

## Security notes
- Token for `/meter/dl` is one-off; after the owner downloads, remove `DL_TOKEN` from the unit (`systemctl edit`) or rotate.
- Revoke ZBook access: on VPS `userdel -r zbtunnel`; on ZBook `sudo userdel -r almaham`.
