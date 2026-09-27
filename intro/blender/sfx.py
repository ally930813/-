"""Synthesise the intro's paper sound effects, synced to intro.py's timeline.

Usage: python sfx.py out.wav   (8 s, 48 kHz, stereo)
"""
import sys
import wave

import numpy as np

SR = 48000
FPS = 24
DUR = 8.0
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

    put(crinkle(1.1, 110, 700, 4500) * np.linspace(0.4, 1, int(1.1 * SR)), 1, 0.4)   # big ball rolls in
    put(thump(95, 0.18, 0.5), 29, 0.3)                                              # wobble taps
    put(thump(105, 0.18, 0.5), 32, 0.2)
    unfold = crinkle(0.9, 190, 1000, 7000) * np.linspace(1, 0.3, int(0.9 * SR))
    put(unfold, 36, 0.6)                                                            # uncrumple
    put(whoosh(0.8, 200, 2200), 38, 0.45)                                           # flies at camera
    put(thump(70, 0.3, 0.2), 57, 0.35)                                              # fills the frame
    put(whoosh(0.9, 180, 1800), 90, 0.4)                                            # pulls back
    put(thump(100, 0.2, 0.4), 120, 0.4)                                             # caught
    put(crinkle(0.25, 180, 1200, 7000), 120, 0.3)
    for i in range(13):                                                             # letters pop
        put(thump(260 + 25 * (i % 4), 0.08, 0.9), 136 + 2 * i, 0.16)
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
