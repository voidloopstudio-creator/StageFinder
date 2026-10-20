#!/usr/bin/env python3
"""Génère la pub vidéo du jour (30 s, 1080x1920) : variantes choisies intelligemment (rotation 'le moins
récemment utilisé'), musique originale générée, rendu, légende + hashtags. Met à jour data/history.json."""
import argparse, json, random, subprocess, shutil, sys, os, itertools, datetime, pathlib
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENG = ROOT / 'engine'
OUT = ROOT / 'out'
HIST = ROOT / 'data' / 'history.json'
LAUNCH = datetime.date(2026, 11, 1)
FEATURES = ['search', 'send', 'track', 'cv']

sys.path.insert(0, str(ENG))
import music

def lru_pick(n, used, rng, avoid=()):
    """used = liste d'indices dans l'ordre chronologique. Choisit l'option jamais utilisée / la plus ancienne."""
    last = {i: -1 for i in range(n)}
    for pos, i in enumerate(used):
        if i is not None and i in last:
            last[i] = pos
    cands = [i for i in range(n) if i not in avoid] or list(range(n))
    m = min(last[i] for i in cands)
    return rng.choice([i for i in cands if last[i] == m])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=None)
    ap.add_argument('--seed', type=int, default=None)
    ap.add_argument('--no-history', action='store_true', help='ne pas écrire dans data/history.json (test)')
    ap.add_argument('--keep-frames', action='store_true')
    a = ap.parse_args()
    today = datetime.date.fromisoformat(a.date) if a.date else datetime.datetime.now(ZoneInfo('Europe/Paris')).date()
    V = json.load(open(ENG / 'variants.json', encoding='utf-8'))
    hist = json.load(open(HIST, encoding='utf-8')) if HIST.exists() else []
    rng = random.Random(a.seed if a.seed is not None else (today.toordinal() * 7919 + len(hist)))
    col = lambda k: [h.get(k) for h in hist]

    perms = list(itertools.permutations(FEATURES))
    perm_keys = ['-'.join(p) for p in perms]
    prev_perm = hist[-1]['order'] if hist else None
    pi = lru_pick(len(perms), [perm_keys.index(h['order']) for h in hist if h.get('order') in perm_keys], rng,
                  avoid=[perm_keys.index(prev_perm)] if prev_perm in perm_keys else ())
    order = list(perms[pi])

    pick = {
        'hook': lru_pick(len(V['hooks']), col('hook'), rng),
        'sector': lru_pick(len(V['sectors']), col('sector'), rng),
        'student': lru_pick(len(V['students']), col('student'), rng),
        'subject': lru_pick(len(V['subjects']), col('subject'), rng),
        'rowsub': lru_pick(len(V['rowsubs']), col('rowsub'), rng),
        'words': lru_pick(len(V['words']), col('words'), rng),
        'fin': lru_pick(len(V['fins']), col('fin'), rng),
        'caption': lru_pick(len(V['captions']), col('caption'), rng),
    }
    for f in FEATURES:
        pick['head_' + f] = lru_pick(len(V['heads'][f]), col('head_' + f), rng)
    pick['head_cvdone'] = lru_pick(len(V['heads']['cvdone']), col('head_cvdone'), rng)

    hook = dict(V['hooks'][pick['hook']]); hook['n'] = rng.randint(*hook['n'])
    sec = V['sectors'][pick['sector']]; stu = V['students'][pick['student']]
    days = (LAUNCH - today).days
    sup = '<sup style="font-size:.55em;vertical-align:top;position:relative;top:.1em">er</sup>'
    if days > 0:
        dispo, dispo2 = f'Disponible le 1{sup} novembre', ('C’est demain.' if days == 1 else f'Plus que {days} jours.')
        dispo_txt = 'Disponible le 1er novembre'
    elif days == 0:
        dispo, dispo2, dispo_txt = 'Disponible aujourd’hui', 'C’est le grand jour.', 'Disponible aujourd’hui'
    else:
        dispo, dispo2, dispo_txt = 'Disponible maintenant', 'Essaie-le dès aujourd’hui.', 'Disponible maintenant'
    music_seed = rng.randint(1, 10**6)
    cfg = {
        'hook': hook, 'order': order, 'tilt': rng.choice([1, -1]),
        'heads': {**{f: V['heads'][f][pick['head_' + f]] for f in FEATURES}, 'cvdone': V['heads']['cvdone'][pick['head_cvdone']]},
        'query': sec['query'], 'comps': sec['comps'], 'to': sec['comps'][1][1],
        'student': {'name': stu['name'], 'sub': f"{stu['klass']} · {sec['city']}"},
        'cvfile': f"CV_{stu['first']}.pdf",
        'body': ['Bonjour,', stu['line'], stu['line2'], f"Merci d’avance, {stu['first']}"],
        'subject': V['subjects'][pick['subject']], 'rowsub': V['rowsubs'][pick['rowsub']],
        'replies': rng.randint(7, 16), 'words': V['words'][pick['words']], 'fin': V['fins'][pick['fin']],
        'dispo': dispo, 'dispo2': dispo2,
    }
    OUT.mkdir(exist_ok=True)
    (ENG / 'cfg.js').write_text('window.CFG=' + json.dumps(cfg, ensure_ascii=False) + ';', encoding='utf-8')

    minfo = music.build(music_seed, str(OUT / 'music.wav'))
    frames = OUT / 'frames'
    shutil.rmtree(frames, ignore_errors=True)
    procs = []
    for lo, hi in [(0, 225), (225, 450), (450, 675), (675, 900)]:
        procs.append(subprocess.Popen([sys.executable, '-I', str(ENG / 'render_frames.py'), str(lo), str(hi), str(frames)]))
    codes = [p.wait() for p in procs]
    if any(codes):
        sys.exit(f'Échec du rendu des images (codes {codes})')
    n = len(list(frames.glob('*.png')))
    if n != 900:
        sys.exit(f'Nombre d’images inattendu: {n}')
    mp4 = OUT / f'StageFinder_{today.isoformat()}.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '30', '-i', str(frames / '%04d.png'),
                    '-i', str(OUT / 'music.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p',
                    '-r', '30', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', str(mp4)], check=True)
    d = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(mp4)]))
    if abs(d - 30) > 0.2 or mp4.stat().st_size < 300_000:
        sys.exit(f'Vidéo invalide (durée {d}, taille {mp4.stat().st_size})')
    if not a.keep_frames:
        shutil.rmtree(frames, ignore_errors=True)

    tags = ['#stagefinder'] + rng.sample([h for h in V['hashtags'] if h != '#stagefinder'], 4)
    caption = V['captions'][pick['caption']] + '\n\n' + dispo_txt + '.\n\n' + ' '.join(tags)
    (OUT / f'caption_{today.isoformat()}.txt').write_text(caption, encoding='utf-8')
    entry = {'date': today.isoformat(), 'order': '-'.join(order), **pick, 'music': minfo, 'replies': cfg['replies'], 'n': hook['n']}
    if not a.no_history:
        hist.append(entry)
        HIST.parent.mkdir(exist_ok=True)
        HIST.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding='utf-8')
    # copie versionnée (le publieur du matin la récupère depuis GitHub) ; on garde 10 jours
    vd = ROOT / 'videos'; vd.mkdir(exist_ok=True)
    shutil.copy(mp4, vd / mp4.name)
    shutil.copy(OUT / f'caption_{today.isoformat()}.txt', vd / f'caption_{today.isoformat()}.txt')
    for old in sorted(vd.glob('StageFinder_*.mp4'))[:-10]:
        old.unlink(); (vd / old.name.replace('StageFinder_', 'caption_').replace('.mp4', '.txt')).unlink(missing_ok=True)
    summary = {'video': str(mp4), 'caption': caption, 'entry': entry}
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
