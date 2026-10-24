#!/usr/bin/env bash
# Deploy/refresh the field web demo on the Contabo VPS (host alias "basira" in ~/.ssh/config).
#   bash lab/webdemo/deploy_contabo.sh            # pulls latest branch on the VPS, syncs models, restarts service
# Models: data/models_<tag>/ dirs are copied with scp (they are not in git).
# Public URL: https://meter.basirapp.site (Caddy on the VPS proxies to 127.0.0.1:8700, see caddy_snippet.txt)
set -euo pipefail
HOST=${HOST:-basira}; REMOTE=/opt/almaham/almaham-3; PORT=8700
# 2026-10-24: live spec = m4 (release candidate loc_m4_s0+rd_m4_s0, first = default in the UI), new (reference), prev, shipped
MODELS=${MODELS:-"m5=data/models_loc_m4_s0_rd_m5_s0 m4=data/models_loc_m4_s0_rd_m4_s0 new=data/models_m1loc_ft6m2_s1 prev=data/models_m1loc_ft6m1 shipped=data/models_repro"}
cd "$(dirname "$0")/../.."
ssh $HOST "cd $REMOTE && git fetch -q origin genspark_ai_developer && git checkout -q genspark_ai_developer && git pull -q --rebase origin genspark_ai_developer && mkdir -p data/webdemo"
SPEC=""
for kv in $MODELS; do
  n=${kv%%=*}; d=${kv#*=}
  ssh $HOST "mkdir -p $REMOTE/$d"; scp -q $d/*.onnx $HOST:$REMOTE/$d/
  SPEC="$SPEC,$n=../../$d"
done
SPEC=${SPEC#,}
ssh $HOST "cat > /etc/systemd/system/almaham-webdemo.service <<UNIT
[Unit]
Description=almaham meter web demo
After=network.target
[Service]
WorkingDirectory=$REMOTE/lab/webdemo
Environment=OMP_NUM_THREADS=2
ExecStart=$REMOTE/.venv/bin/python3 server.py $SPEC $PORT $REMOTE/data/webdemo
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload && systemctl enable -q almaham-webdemo && systemctl restart almaham-webdemo && sleep 3 && curl -s 127.0.0.1:$PORT/health"
echo
