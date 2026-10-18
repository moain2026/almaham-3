set -e
N=$1
cd ~/repos/almaham-3/lab
python3 /tmp/opencode/consensus.py $N
rm -f ../data/erp/labels/labeller_1_0*.csv.bak
# keep only the latest cumulative file
for f in ../data/erp/labels/labeller_1_*.csv; do [ "$f" = "../data/erp/labels/labeller_1_$(printf %04d $N).csv" ] || rm "$f"; done
python3 erp_label.py merge ../data/erp/labels ../benchmark/data/erp/labels_slice_1.csv
rm -f ../benchmark/data/erp/conflicts.csv
python3 erp_label.py stats ../benchmark/data/erp/labels_slice_1.csv | tee /tmp/opencode/stats.txt
cd ..
TOT=$(awk '/^total/{print $2}' /tmp/opencode/stats.txt); X=$(awk '/^total/{print $5}' /tmp/opencode/stats.txt); P=$(awk '/^total/{print $8}' /tmp/opencode/stats.txt)
git fetch -q && git stash -q -u 2>/dev/null || true
git rebase -q origin/genspark_ai_developer
git stash pop -q 2>/dev/null || true
python3 - "$TOT" "$X" "$P" <<'PY'
import sys,re
tot,x,p=sys.argv[1:]
s=open('STATUS.md').read()
s=re.sub(r'- labels slice 1: .*', f'- labels slice 1: {tot} done, {int(x)+int(p)} unreadable ({p} P) — تسمية آلية بنموذج رؤية لا بشرية: 3 قراءات مستقلة على العرض المكبّر + فحص رابع خانةً خانة على الصورة الأصلية؛ يُقبل الرقم فقط إذا اتفقت الأربعة وإلا X. مراجعة يدوية: 20 صورة من 0–200 بلا أخطاء، و24 من 1600–2400 فيها خطأان مُجمَع عليهما (TAGADOD 001418 قُرئ 007478؛ 008248 قُرئ 008290) رفضهما الفحص الرابع فأُضيف بأثر رجعي', s)
open('STATUS.md','w').write(s)
PY
git add benchmark/data/erp/labels_slice_1.csv STATUS.md
git -c user.name="Ethan Zhao" -c user.email="genspark_dev@genspark.ai" commit -qm "data(erp): labels slice 1, $TOT photos"
timeout 60 git push -q origin HEAD:genspark_ai_developer
git log --oneline -1
