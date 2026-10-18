cd /home/user/repos/almaham-3/lab
for s in vlm vlm2 vlm3; do setsid nohup python3 /tmp/opencode/$s.py > /tmp/opencode/$s.log 2>&1 < /dev/null & done
