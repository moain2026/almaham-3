#!/usr/bin/env bash
# usage: eval_one.sh <loc.pt> <rd.pt> <tag>
cd /home/user/webapp/lab && source ../.venv/bin/activate
export TORCH_THREADS=1 OMP_NUM_THREADS=1
bash eval_ckpt.sh "$1" "$2" "$3" > logs/eval_$3.log 2>&1
python3 eval_testset_human.py ../data/models_$3 $3 >> logs/eval_$3.log 2>&1
python3 risk_coverage.py ../data/models_$3 $3 >> logs/eval_$3.log 2>&1
echo "DONE $3" >> logs/eval_$3.log
