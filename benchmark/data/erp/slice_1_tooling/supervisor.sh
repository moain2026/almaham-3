#!/bin/bash
# re-ship cumulative labels at the largest N (multiple of 200) for which all 4 layers are complete
LAST=0; TARGET=${1:-5916}
while true; do
  for s in vlm vlm2 vlm3; do pgrep -f "python3 /tmp/opencode/$s.py" >/dev/null || (cd /home/user/repos/almaham-3/lab && setsid nohup python3 /tmp/opencode/$s.py >> /tmp/opencode/$s.log 2>&1 < /dev/null &); done
  BEST=0
  for N in $(seq 200 200 $TARGET) $TARGET; do
    python3 /tmp/opencode/consensus.py $N | grep -q "missing 0$" && BEST=$N || break
  done
  if [ $BEST -ge $((LAST+200)) ] || { [ $BEST -eq $TARGET ] && [ $LAST -ne $TARGET ]; }; then
    bash /tmp/opencode/ship.sh $BEST >> /tmp/opencode/ship.log 2>&1 && echo "SHIPPED $BEST $(date -u +%H:%M)" >> /tmp/opencode/super.log && LAST=$BEST || echo "SHIPFAIL $BEST" >> /tmp/opencode/super.log
  fi
  [ $LAST -eq $TARGET ] && { echo DONE2 >> /tmp/opencode/super.log; exit 0; }
  sleep 60
done
