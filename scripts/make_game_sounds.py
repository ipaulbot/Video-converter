"""Synthesise BallBuster XT's sound effects into graphics/balls/sfx/*.wav.

Ten short 8-bit-style effects, 22 050 Hz 16-bit mono, each under 0.6 s,
built from square / triangle / noise with simple envelopes -- plain `wave`
and `math`, no numpy. Run from the repo root:

    python scripts/make_game_sounds.py

The files are committed; the PyInstaller spec bundles all of graphics/.
Regenerate only when changing a sound (the output is deterministic).
"""
from __future__ import annotations

import math
import os
import random
import struct
import sys
import wave

RATE = 22050
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "graphics", "balls", "sfx")


def _square(freq, t):
    return 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0


def _triangle(freq, t):
    return 2.0 * abs(2.0 * ((freq * t) % 1.0) - 1.0) - 1.0


def _decay(t, length, power=1.0):
    return max(0.0, 1.0 - t / length) ** power


def tone(length, freq_start, freq_end=None, wave_fn=_square, volume=0.5, power=1.5, rng=None):
    """A note sliding from freq_start to freq_end with a linear-ish decay."""
    freq_end = freq_start if freq_end is None else freq_end
    samples = []
    n = int(RATE * length)
    phase_t = 0.0
    for i in range(n):
        t = i / RATE
        freq = freq_start + (freq_end - freq_start) * (i / max(1, n - 1))
        phase_t += freq / RATE
        value = wave_fn(1.0, phase_t) * _decay(t, length, power) * volume
        samples.append(value)
    return samples


def noise(length, volume=0.4, power=2.0, seed=1):
    rng = random.Random(seed)
    n = int(RATE * length)
    return [rng.uniform(-1, 1) * _decay(i / RATE, length, power) * volume for i in range(n)]


def mix(*parts):
    length = max(len(p) for p in parts)
    out = [0.0] * length
    for part in parts:
        for i, v in enumerate(part):
            out[i] += v
    peak = max(1.0, max(abs(v) for v in out))
    return [v / peak for v in out]


def seq(*parts):
    out = []
    for part in parts:
        out.extend(part)
    return out


def write(name, samples):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{name}.wav")
    with wave.open(path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(RATE)
        frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32000)) for s in samples)
        fh.writeframes(frames)
    return path


def build():
    sounds = {
        "shoot": tone(0.12, 880, 440, volume=0.45),
        "bounce": tone(0.06, 520, 480, wave_fn=_triangle, volume=0.5, power=1.0),
        "stick": mix(tone(0.08, 240, 200, wave_fn=_triangle, volume=0.5), noise(0.04, 0.15)),
        "pop": seq(tone(0.07, 660, volume=0.45), tone(0.10, 990, volume=0.45)),
        "pop2": seq(tone(0.07, 784, volume=0.45), tone(0.10, 1175, volume=0.45)),
        "pop3": seq(tone(0.06, 880, volume=0.45), tone(0.06, 1319, volume=0.45), tone(0.10, 1760, volume=0.45)),
        "drop": tone(0.18, 500, 180, wave_fn=_triangle, volume=0.4, power=1.0),
        "bomb": mix(noise(0.45, 0.6, power=1.5, seed=3), tone(0.35, 120, 40, wave_fn=_triangle, volume=0.5, power=1.0)),
        "reel": tone(0.03, 1400, 1400, volume=0.3, power=1.0),
        "payout": seq(tone(0.08, 523, volume=0.45), tone(0.08, 659, volume=0.45), tone(0.08, 784, volume=0.45),
                      tone(0.22, 1047, volume=0.5, power=1.0)),
        "level": seq(tone(0.09, 392, volume=0.45), tone(0.09, 523, volume=0.45), tone(0.09, 659, volume=0.45),
                     tone(0.09, 784, volume=0.45), tone(0.20, 1047, volume=0.5, power=1.0)),
        "over": seq(tone(0.16, 392, 370, volume=0.45), tone(0.16, 330, 311, volume=0.45),
                    tone(0.26, 262, 196, volume=0.45, power=1.0)),
    }
    written = [write(name, samples) for name, samples in sounds.items()]
    return written


if __name__ == "__main__":
    for path in build():
        print(os.path.relpath(path), os.path.getsize(path), "bytes")
    sys.exit(0)
