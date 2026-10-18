"""Private local CLI for profile enrollment, reading and inspectable HTML reports.

Examples:
 python lab/profile_cli.py demo --out data/profile_sprint/public/demo.html
 python lab/profile_cli.py enroll --image data/reference.png --profile data/meter.json --digits 6
 python lab/profile_cli.py read --profile data/meter.json --images data/frame1.png data/frame2.png --out data/result.html
Profiles include private reference pixels. All output paths MUST stay under data/.
"""
import argparse
import base64
import html
import io
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from bench_profile_reader import occlude, render_scene, synthetic_profile
import paths
import profile_reader as pr
from profile_policy import require_observed_segments
import sevenseg as v1


MAX_FILE_BYTES = 20_000_000


def private_output(path):
    path = Path(path).resolve()
    if not path.is_relative_to(paths.DATA.resolve()):
        raise ValueError('private image/profile outputs must be inside data/ (git ignored)')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def decode_image(raw):
    # Read dimensions before OpenCV allocates decoded pixels (compressed images
    # can be tiny on disk but enormous in memory).
    with Image.open(io.BytesIO(raw)) as header:
        w, h = header.size
        if min(w, h) < 8 or w * h > pr.DEFAULT.max_pixels:
            raise ValueError('decoded image dimensions outside supported limits')
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    pr.validate_image(image)
    return image


def read_image(path):
    p = Path(path)
    if p.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('image file exceeds 20 MB')
    return decode_image(p.read_bytes())


def png_b64(image):
    ok, encoded = cv2.imencode('.png', image)
    if not ok:
        raise ValueError('PNG encoding failed')
    return base64.b64encode(encoded).decode('ascii')


def save_profile(profile, destination):
    profile.validate()
    payload = profile.metadata()
    payload['template_png_base64'] = png_b64(profile.template)
    private_output(destination).write_text(json.dumps(payload, indent=2) + '\n')


def load_profile(source):
    source = Path(source)
    if source.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('profile exceeds 20 MB')
    obj = json.loads(source.read_text())
    if obj.get('version') != 1 or not isinstance(obj.get('verified'), bool):
        raise ValueError('invalid profile schema/version')
    raw = base64.b64decode(obj['template_png_base64'], validate=True)
    image = decode_image(raw)
    if obj['template_sha256'] != pr.image_hash(image):
        raise ValueError('profile reference pixels failed SHA256 verification')
    if obj['size'] != [image.shape[1], image.shape[0]]:
        raise ValueError('profile dimensions mismatch')
    profile = pr.Profile(tuple(tuple(c) for c in obj['cells']), image, float(obj['shear']),
                         obj['verified'], str(obj['name']))
    profile.validate()
    return profile


def overlay(image, profile, observation, register):
    aligned, _, alignment = pr.align_frame(image, profile, register)
    out = aligned.copy()
    for i, (cell, states) in enumerate(zip(profile.cells, observation['states'])):
        x0, y0, x1, y1 = cell
        for segment, state in zip(v1.SEG_ORDER, states):
            a, b, c, d = v1.WIN[segment]
            p = (round(x0 + a * (x1 - x0)), round(y0 + b * (y1 - y0)))
            q = (round(x0 + c * (x1 - x0)), round(y0 + d * (y1 - y0)))
            color = (40, 190, 40) if state == 1 else (170, 170, 170) if state == 0 else (0, 160, 250)
            cv2.rectangle(out, p, q, color, 1)
        cv2.putText(out, str(i + 1), (round(x0), max(10, round(y0) - 3)), 0, .35, (30, 30, 250), 1)
    return out, alignment


def scenario_html(title, frames, profile, register=False):
    result = require_observed_segments(pr.read_frames(frames, profile, register))
    lookup = {pr.image_hash(frame): frame for frame in frames}
    cards = []
    for number, observation in enumerate(result['observations'], 1):
        image = lookup[observation['input_sha256']]
        marked, _ = overlay(image, profile, observation, register)
        top = html.escape(observation.get('top1') or '—')
        status = html.escape(observation['status'])
        cards.append(f'<article><h3>الإطار {number}</h3><img alt="الصورة الداخلة" src="data:image/png;base64,{png_b64(image)}">'
                     f'<img alt="خريطة المقاطع" src="data:image/png;base64,{png_b64(marked)}">'
                     f'<p>أفضل احتمال تشخيصي: <b>{top}</b> · الحالة: <code>{status}</code></p></article>')
    accepted = bool(result['value'])
    label = html.escape(result['value']) if accepted else 'لا تُعبّأ القراءة'
    evidence = ' / '.join('{' + ','.join(c) + '}' for c in result.get('candidates', []))
    section = (f'<section><h2>{html.escape(title)}</h2><div class="result {"ok" if accepted else "hold"}">'
               f'{label}<small>{html.escape(result["status"])}</small></div>'
               f'<div class="cards">{"".join(cards)}</div><p class="digits" dir="ltr">{html.escape(evidence)}</p>'
               f'<details><summary>دليل JSON كامل</summary><pre dir="ltr">{html.escape(json.dumps(result, indent=2, ensure_ascii=False))}</pre></details></section>')
    return section, result


def document(sections, synthetic):
    warning = ('هذه صور مولدة برمجيًا، وليست عدادات عملاء أو إثبات دقة ميدانية.' if synthetic else
               'هذا التقرير يتضمن صورك الخاصة. لا تنشره أو ترفعه إلى المستودع العام.')
    return '''<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><link rel="icon" href="data:,">
<title>مختبر قراءة العداد — الدليل قبل الرقم</title><style>
*{box-sizing:border-box}body{margin:0;background:#0d1524;color:#e2e9f6;font:17px/1.8 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:36px 20px}header{padding:24px 0}h1{font-size:34px;margin:6px 0}
h2{font-size:23px}p{color:#bcc9df}.tag{color:#54d2b0;letter-spacing:1px}section{background:#162238;border:1px solid #2c3b54;border-radius:16px;padding:24px;margin:24px 0}
.notice{border-right:4px solid #ffbc55;background:#2a2730;padding:16px;border-radius:5px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}article{background:#101b2f;padding:14px;border-radius:10px}
img{width:100%;height:auto;margin:6px 0;image-rendering:auto}code,pre{direction:ltr;font-size:13px}pre{overflow:auto;max-height:400px;padding:16px;background:#091322}summary{cursor:pointer}.result{font-size:30px;font-weight:700;padding:14px;margin-bottom:18px;border-radius:8px}.ok{color:#74e2b2;background:#12392e}.hold{color:#ffcc83;background:#3b2e1d}small{display:block;font-size:13px;font-weight:400}.digits{overflow-wrap:anywhere;color:#adc1de}a{color:#78c9ff}footer{margin-top:30px;font-size:14px}
</style><main><header><div class="tag">OFFLINE · NO TRAINING · RESEARCH ONLY</div><h1>الدليل قبل الرقم</h1>
<p>قالب هندسي + محاذاة + كشف فقد المقاطع + دمج أدلة الإطارات. لا تُنسخ أرقام صورة القالب.</p></header>
<div class="notice">''' + html.escape(warning) + '''<br>الأخضر: مقطع ظاهر · الرمادي: غير ظاهر · البرتقالي: غير محسوم.
كل نتيجة خضراء مشروطة بافتراضات التجربة، وليست ثقة معايرة أو إذن فوترة آلية.</div>''' + ''.join(sections) + '''
<footer>التنفيذ والاختبارات وسجل الاستكمال: <a href="https://github.com/moain2026/almaham-3/pull/2">طلب الدمج التجريبي #2</a>.
لا إنترنت مطلوب لحساب النتائج؛ هذا الملف عرض محلي لنتائج محسوبة بالفعل، وليس خدمة رفع صور.</footer></main></html>'''


def write_report(path, sections, results, synthetic):
    path = private_output(path)
    if path.suffix.lower() != '.html':
        raise ValueError('report output must use .html extension')
    path.write_text(document(sections, synthetic))
    # Never overwrite a same-stem profile JSON during enrollment preview.
    path.with_suffix('.result.json').write_text(json.dumps(results, indent=2, ensure_ascii=False) + '\n')
    return path


def demo(destination):
    profile = synthetic_profile()
    frame = render_scene('123456')
    first, second = occlude(frame, 130, 158), occlude(frame, 230, 258)
    matrix = cv2.getRotationMatrix2D((177, 74), 1.5, 1.)
    matrix[:, 2] += (2, -1)
    moved = cv2.warpAffine(frame, matrix, (354, 148), borderMode=cv2.BORDER_REFLECT)
    cases = [('1 — شاشة واضحة، وقالب المرجع يعرض رقمًا مختلفًا', [frame], False),
             ('2 — إطار محجوب: الامتناع بدل التخمين', [first], False),
             ('3 — الإطار الثاني محجوب في موضع آخر', [second], False),
             ('4 — دمج المقاطع المرئية يستعيد القراءة', [first, second], False),
             ('5 — تسجيل هندسي بعد تحريك الكاميرا', [moved], True),
             ('6 — الشاشة تغيّرت بين الإطارين: لا نركّب رقمًا هجينًا', [frame, render_scene('123457')], False)]
    sections, results = [], []
    for title, images, register in cases:
        section, result = scenario_html(title, images, profile, register)
        sections.append(section)
        results.append({'scenario': title, 'result': result})
    return write_report(destination, sections, results, True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    de = sub.add_parser('demo')
    de.add_argument('--out', type=Path, default=paths.DATA / 'profile_sprint/public/demo.html')
    en = sub.add_parser('enroll')
    en.add_argument('--image', required=True)
    en.add_argument('--profile', type=Path, required=True)
    en.add_argument('--digits', type=int, default=6)
    en.add_argument('--cells', type=Path, help='explicit [x0,y0,x1,y1] cells in original image coordinates')
    en.add_argument('--confirm-layout', action='store_true', help='human confirms integer-cell geometry, NOT reference value')
    rd = sub.add_parser('read')
    rd.add_argument('--profile', required=True)
    rd.add_argument('--images', nargs='+', required=True)
    rd.add_argument('--out', type=Path, required=True)
    rd.add_argument('--already-aligned', action='store_true', help='explicitly disable automatic registration')
    args = parser.parse_args()
    cv2.setNumThreads(1)
    try:
        if args.command == 'demo':
            print(demo(args.out))
        elif args.command == 'enroll':
            image = read_image(args.image)
            if args.cells:
                cells = json.loads(args.cells.read_text())
                if len(cells) != args.digits:
                    raise ValueError('explicit cells must match --digits')
                profile = pr.Profile(tuple(tuple(c) for c in cells), image, verified=args.confirm_layout)
            else:
                profile = pr.enroll(image, args.digits, args.confirm_layout)
            save_profile(profile, args.profile)
            # Always emit a layout preview, even for unconfirmed enrollment.
            section, result = scenario_html('معاينة هندسة الخانات — راجعها قبل الاعتماد', [image], profile, False)
            report = write_report(args.profile.with_suffix('.html'), [section], result, False)
            print(json.dumps({'profile': str(args.profile), 'preview': str(report), 'verified': profile.verified}))
        else:
            profile = load_profile(args.profile)
            images = [read_image(p) for p in args.images]
            section, result = scenario_html('نتيجة صور المستخدم — لا ضمان ميداني بعد', images, profile, not args.already_aligned)
            print(write_report(args.out, [section], result, False))
            print(json.dumps({'value': result['value'], 'status': result['status']}, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
