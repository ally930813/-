"""Synthesise the intro's paper sound effects, synced to intro.py's timeline.

Usage: python sfx.py out.wav   (7 s, 48 kHz, stereo)
"""
import sys
import wave

import numpy as np

SR = 48000
FPS = 24
DUR = 7.0
rng = np.random.default_rng(4)


def t_of(frame):
    return (frame - 1) / FPS


def band_noise(n, lo, hi):
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n)
    return x / (np.abs(x).max() + 1e-9)


def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def crinkle(dur, density, lo=1500, hi=9000):
    """Paper crinkle: a cloud of tiny band-limited crackles."""
    n = int(dur * SR)
    out = np.zeros(n)
    for _ in range(int(density * dur)):
        s = rng.integers(0, n)
        ln = int(rng.uniform(0.004, 0.02) * SR)
        g = band_noise(ln, lo, hi) * env(ln, 0.0005, rng.uniform(0.002, 0.008)) * rng.uniform(0.2, 1)
        out[s:s + ln] += g[: n - s]
    return out


def thump(freq=70, dur=0.35, click=0.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * freq * t * (1 - 0.3 * t)) * env(n, 0.001, 0.07)
    hit = band_noise(n, 800, 5000) * env(n, 0.0003, 0.012) * click
    return body + hit


def whoosh(dur, lo=300, hi=3000):
    n = int(dur * SR)
    x = band_noise(n, lo, hi)
    shape = np.sin(np.linspace(0, np.pi, n)) ** 2
    return x * shape


def main(path):
    n = int(DUR * SR)
    mix = np.zeros(n)

    def put(x, frame, gain):
        s = int(t_of(frame) * SR)
        e = min(n, s + len(x))
        mix[s:e] += gain * x[: e - s]

    put(crinkle(1.25, 90, 800, 5000) * np.linspace(0.4, 1, int(1.25 * SR)), 1, 0.35)  # roll in
    put(thump(110, 0.15, 0.6), 34, 0.25)                                            # wobble taps
    put(thump(120, 0.15, 0.6), 37, 0.18)
    put(crinkle(0.7, 420), 40, 0.6)                                                 # burst + uncrumple
    put(whoosh(0.35, 500, 4000), 40, 0.35)
    put(whoosh(0.35, 400, 2500), 62, 0.25)                                          # hop out
    put(thump(90, 0.25, 0.3), 77, 0.45)                                             # landing
    put(thump(62, 0.45, 0.8), 84, 1.0)                                              # STAMP
    put(crinkle(0.25, 200), 84, 0.3)
    put(thump(95, 0.2, 0.3), 96, 0.3)                                               # proud hop land
    put(whoosh(0.55, 250, 3500), 127, 0.6)                                          # flip
    put(crinkle(0.3, 260, 1200, 7000), 139, 0.45)                                   # paper flap settle
    put(thump(140, 0.12, 0.8), 140, 0.25)

    mix = np.tanh(mix * 1.2) * 0.8
    fade = int(0.25 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)
    stereo = np.stack([mix, np.roll(mix, 24)], axis=1)  # tiny width
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    main(sys.argv[1])
