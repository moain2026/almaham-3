#!/bin/bash
TARGET=${1:-4000}; NEXT=${2:-2600}
while [ $NEXT -le $TARGET ]; do
  for s in vlm vlm2 vlm3; do pgrep -f "python3 /tmp/opencode/$s.py" >/dev/null || (cd /home/user/repos/almaham-3/lab && setsid nohup python3 /tmp/opencode/$s.py >> /tmp/opencode/$s.log 2>&1 < /dev/null &); done
  if python3 /tmp/opencode/consensus.py $NEXT | grep -q "missing 0$"; then
    bash /tmp/opencode/ship.sh $NEXT >> /tmp/opencode/ship.log 2>&1 && echo "SHIPPED $NEXT $(date -u +%H:%M)" >> /tmp/opencode/super.log || echo "SHIPFAIL $NEXT" >> /tmp/opencode/super.log
    NEXT=$((NEXT+200))
  fi
  sleep 30
done
echo DONE >> /tmp/opencode/super.log
