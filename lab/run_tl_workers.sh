#!/usr/bin/env bash
# launch text_locate workers: run_tl_workers.sh <shards e.g. "0 1 2"> <n> <skipfiles>
cd "$(dirname "$0")"; source ../.venv/bin/activate
T=CRYSTAL,SMART_YELLOW,TAGADOD,OTHER,KENWELL,MECHANICAL,GLORY,HPL,CHINT,TOMAS_STATIC,TOMAS_SMART
for i in $1; do
  TORCH_THREADS=1 setsid nohup python3 text_locate.py weights/reader_ft6m1_augv2.pt ../data/erp/ft/text_locate_p5_$i.json --verified-only --types $T --shard $i/$2 --skip "$3" > logs/text_locate_p5_$i.log 2>&1 < /dev/null &
done
