"""Génère une instrumentale originale (142 BPM, 30 s) calée sur la grille de beats de la pub.
Structure : intro 16 temps (pad + pluck, montée), drop au temps 16, outro avec impact au temps 60.
Tout est synthétisé par code (numpy) : aucune musique tierce, aucun problème de droits."""
import numpy as np, wave, sys, json

SR = 44100
BPM = 142.0
BEAT = 60.0 / BPM
DUR = 30.0
N = int(SR * DUR)

PROGS = {
    "mineur_classique": [(0, 'm'), (8, 'M'), (3, 'M'), (10, 'M')],
    "mineur_sombre":    [(0, 'm'), (5, 'm'), (8, 'M'), (7, 'M')],
    "majeur_pop":       [(0, 'M'), (7, 'M'), (9, 'm'), (5, 'M')],
    "majeur_relatif":   [(9, 'm'), (5, 'M'), (0, 'M'), (7, 'M')],
    "mineur_epique":    [(0, 'm'), (3, 'M'), (10, 'M'), (5, 'm')],
}
ARPS = {
    "montee":   [0, 1, 2, 3, 2, 1, 2, 4],
    "zigzag":   [0, 2, 1, 3, 2, 4, 3, 5],
    "pulse":    [0, 0, 2, 2, 1, 1, 3, 3],
    "ruban":    [0, 2, 4, 5, 4, 2, 1, 3],
}
BASSES = {
    "croches":  [1, 0, 1, 0, 1, 0, 1, 0],
    "syncope":  [1, 0, 0, 1, 0, 1, 0, 0],
    "rebond":   [1, 1, 0, 1, 1, 0, 1, 0],
}
KICKS = ["four", "broken"]
ROOTS = [45, 47, 48, 50, 52, 53]  # A2 B2 C3 D3 E3 F3
CHORD = {'m': (0, 3, 7), 'M': (0, 4, 7)}


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def saw(f, n, nh=10, ph=0.0):
    t = np.arange(n) / SR
    nh = max(1, min(nh, int(9000 / f)))
    y = np.zeros(n)
    for h in range(1, nh + 1):
        y += np.sin(2 * np.pi * f * h * t + ph * h) / h
    return y * (2 / np.pi)


def put(buf, start, sig, gain=1.0):
    i = int(start * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[:j - i] * gain


def kick(rng, pitch=48):
    n = int(0.38 * SR)
    t = np.arange(n) / SR
    f = pitch + 110 * np.exp(-t * 32)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-t * 7.5)
    y += 0.25 * np.exp(-t * 400) * rng.standard_normal(n)
    return y


def clap(rng):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    nz = rng.standard_normal(n)
    nz = np.diff(nz, prepend=0)
    env = np.exp(-t * 22) + 0.6 * np.exp(-np.mod(t, 0.012) * 80) * (t < 0.04)
    return nz * env * 0.5 + 0.3 * np.sin(2 * np.pi * 185 * t) * np.exp(-t * 28)


def hat(rng, open_=False):
    n = int((0.22 if open_ else 0.07) * SR)
    t = np.arange(n) / SR
    nz = np.diff(rng.standard_normal(n), prepend=0)
    return nz * np.exp(-t * (14 if open_ else 70)) * 0.35


def crash(rng, length=1.8):
    n = int(length * SR)
    t = np.arange(n) / SR
    nz = np.diff(rng.standard_normal(n), n=2, prepend=[0, 0])
    return nz * np.exp(-t * 2.4) * 0.35


def riser(rng, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    x = t / length
    f = 180 + 2400 * x ** 2
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * x ** 1.5 * 0.25
    nz = np.diff(rng.standard_normal(n), prepend=0) * x ** 2.2 * 0.35
    return y + nz


def adsr(n, a, r):
    e = np.ones(n)
    na = max(1, int(a * SR)); nr = max(1, int(r * SR))
    e[:na] = np.linspace(0, 1, na)
    e[-nr:] *= np.linspace(1, 0, nr)
    return e


def build(seed, out_wav):
    rng = np.random.default_rng(seed)
    prog_name = rng.choice(list(PROGS))
    arp_name = rng.choice(list(ARPS))
    bass_name = rng.choice(list(BASSES))
    kick_name = rng.choice(KICKS)
    root = int(rng.choice(ROOTS))
    kick_pitch = int(rng.integers(44, 54))
    prog = PROGS[prog_name]; arp = ARPS[arp_name]; bp = BASSES[bass_name]

    L = np.zeros(N); R = np.zeros(N)       # couches stéréo mix
    pad = np.zeros(N); pluck = np.zeros(N); bass = np.zeros(N); drums = np.zeros(N); fx = np.zeros(N)
    kick_env = np.zeros(N)
    total_beats = int(DUR / BEAT) + 1       # 71
    bars = int(np.ceil(total_beats / 4))

    def chord_notes(bar):
        r_off, q = prog[bar % 4]
        r = root + r_off
        iv = CHORD[q]
        return [r + iv[0], r + iv[1], r + iv[2]]

    for bar in range(bars):
        t0 = bar * 4 * BEAT
        notes = chord_notes(bar)
        # pad : accord tenu (3 notes x 2 saws désaccordés), 1 octave au-dessus
        n = int(4 * BEAT * SR)
        env = adsr(n, 0.25, 0.35)
        for m in notes:
            for det in (-0.07, 0.07):
                put(pad, t0, saw(mtof(m + 12 + det), n, 6) * env, 0.11)
        # basse
        for i in range(8):
            if bp[i]:
                ts = t0 + i * BEAT / 2
                nn = int(BEAT / 2 * 0.95 * SR)
                m = notes[0] - 12 + (12 if (bass_name == "rebond" and i % 4 == 3) else 0)
                tt = np.arange(nn) / SR
                y = (np.sin(2 * np.pi * mtof(m) * tt) + 0.35 * saw(mtof(m), nn, 5)) * np.exp(-tt * 5.5)
                put(bass, ts, y * adsr(nn, 0.004, 0.02), 0.5)
        # pluck / arpège (8 croches par mesure)
        tones = [notes[0] + 12, notes[1] + 12, notes[2] + 12, notes[0] + 24, notes[1] + 24, notes[2] + 24]
        for i in range(8):
            ts = t0 + i * BEAT / 2
            nn = int(BEAT * 1.4 * SR)
            tt = np.arange(nn) / SR
            m = tones[arp[i]]
            y = saw(mtof(m), nn, 9) * np.exp(-tt * 9.0)
            put(pluck, ts, y * adsr(nn, 0.003, 0.05), 0.20)

    # --- batterie ---
    drop = 16 * BEAT
    k = kick(rng, kick_pitch); c = clap(rng); h = hat(rng); oh = hat(rng, True)
    for b in range(total_beats):
        tb = b * BEAT
        if tb >= DUR:
            break
        in_drop = (16 <= b < 60)
        if in_drop:
            kick_pattern = [True] if kick_name == "four" else [b % 4 in (0, 1, 3)]
            if kick_pattern[0]:
                put(drums, tb, k, 0.95); put(kick_env, tb, np.ones(1), 1.0)
            if b % 4 in (1, 3):
                put(drums, tb, c, 0.55)
            put(drums, tb, h, 0.5)
            put(drums, tb + BEAT / 2, oh if b % 2 == 1 else h, 0.55)
            if b % 4 == 3:
                put(drums, tb + BEAT * 0.75, h, 0.35)
        elif 8 <= b < 16:
            put(drums, tb + BEAT / 2, h, 0.20 + 0.02 * (b - 8))
            if b >= 12:
                put(drums, tb, k, 0.28 + 0.1 * (b - 12))
                put(kick_env, tb, np.ones(1), 0.5)
        elif 60 <= b < 64:
            put(drums, tb + BEAT / 2, h, 0.25)
            if b % 2 == 0:
                put(drums, tb, k, 0.5); put(kick_env, tb, np.ones(1), 0.4)
    # roulement de caisse claire avant le drop (temps 14-16, croches puis doubles)
    for i in range(8):
        ts = (14 * BEAT) + i * BEAT / 4
        put(drums, ts, c, 0.18 + 0.05 * i)
    # effets : riser (temps 10 -> 16), impacts au drop et à la finale
    put(fx, 10 * BEAT, riser(rng, 6 * BEAT), 0.8)
    put(fx, drop, crash(rng), 0.9); put(fx, drop, kick(rng, 40), 0.8)
    put(fx, 60 * BEAT, crash(rng, 2.2), 0.8); put(fx, 60 * BEAT, kick(rng, 40), 0.8)

    # --- enveloppe d'ouverture (intro filtrée = moins de pluck, plus de pad) ---
    t = np.arange(N) / SR
    beat_pos = t / BEAT
    intro_gain = np.where(beat_pos < 16, 0.55 + 0.45 * np.clip((beat_pos - 8) / 8, 0, 1), 1.0)
    outro = np.where(beat_pos >= 60, 0.8, 1.0)
    # sidechain : creux à chaque kick
    duck = np.ones(N)
    kb = np.nonzero(kick_env > 0)[0]
    d_len = int(0.28 * SR)
    shape = 1 - 0.65 * np.exp(-np.arange(d_len) / SR * 14)
    for i in kb:
        j = min(N, i + d_len)
        duck[i:j] = np.minimum(duck[i:j], shape[:j - i])

    # stéréo : pad et pluck décalés (Haas) + écho léger sur pluck
    def delayed(x, ms):
        d = int(ms / 1000 * SR); y = np.zeros_like(x); y[d:] = x[:-d]; return y
    echo = np.zeros(N); d = int(BEAT * 0.75 * SR); echo[d:] = pluck[:-d] * 0.35
    pl = pluck + echo
    mid = (pad * 0.9 + pl * 0.8 + bass) * duck * intro_gain * outro + drums + fx
    left = mid + delayed(pad, 12) * 0.25 + delayed(pl, 9) * 0.15
    right = mid + delayed(pad, 22) * 0.25 + delayed(pl, 17) * 0.15
    y = np.stack([left, right], 1)
    y = np.tanh(y * 1.25) / np.tanh(1.25)
    y /= max(1e-9, np.abs(y).max()); y *= 0.89
    fi = int(0.2 * SR); y[:fi] *= np.linspace(0, 1, fi)[:, None]
    fo = int(2.4 * SR); y[-fo:] *= (0.5 * (1 + np.cos(np.linspace(0, np.pi, fo))))[:, None]
    pcm = (y * 32767).astype('<i2')
    with wave.open(out_wav, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    return {"seed": int(seed), "prog": str(prog_name), "arp": str(arp_name), "bass": str(bass_name),
            "kick": str(kick_name), "root": root, "kick_pitch": kick_pitch}


if __name__ == "__main__":
    info = build(int(sys.argv[1]), sys.argv[2])
    print(json.dumps(info))
