# -*- coding: utf-8 -*-
"""WSOLA self-check: duration ratio, pitch preservation, no clipping.

Run: python tests/test_stretch.py
Requires numpy; exits 0 and prints SKIP when numpy is unavailable.
"""
import importlib.util
import math
import os
import sys
import time

try:
    import numpy as np
except ImportError:
    print("SKIP: numpy is not installed")
    sys.exit(0)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("saymod", os.path.join(ROOT, "say.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SR = 24000
n = SR  # 1 second
t = np.arange(n) / SR
freq = 440.0
sig = 0.5 * np.sin(2 * math.pi * freq * t)
env = np.minimum(1.0, np.minimum(t / 0.05, (1 - t) / 0.05))
sig = (sig * env * 32767).astype("<i2").tobytes()


def zero_cross_freq(pcm):
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
    x = x - x.mean()
    s = np.sign(x)
    s[s == 0] = 1
    zc = np.sum(s[1:] != s[:-1])
    return zc / 2.0 / (len(x) / SR)


failures = 0
for rate in (0.8, 1.0, 1.25):
    t0 = time.time()
    out = m.stretch(sig, rate)
    dt = time.time() - t0
    y = np.frombuffer(out, dtype="<i2")
    dur = len(y) / SR
    f = zero_cross_freq(out)
    peak = float(np.abs(y).max()) / 32767
    ok = abs(dur * rate - 1.0) < 0.02 and abs(f - freq) < freq * 0.03 and peak <= 1.0
    failures += 0 if ok else 1
    print("rate=%.2f  dur=%.3fs (expect %.3f)  freq=%.1fHz (expect %.0f)  peak=%.2f  time=%.3fs  %s"
          % (rate, dur, 1.0 / rate, f, freq, peak, dt, "OK" if ok else "FAIL"))

rng = np.random.default_rng(0)
noise = rng.normal(0, 0.2, SR).astype(np.float32)
buzz = (noise * np.minimum(1, np.minimum(t / 0.05, (1 - t) / 0.05)) * 32767).astype("<i2").tobytes()
for rate in (0.85, 1.15):
    y = np.frombuffer(m.stretch(buzz, rate), dtype="<i2")
    nan = bool(np.isnan(y.astype(np.float32)).any())
    peak = float(np.abs(y.astype(np.int32)).max()) / 32767
    ok = (not nan) and peak <= 1.0
    failures += 0 if ok else 1
    print("noise rate=%.2f dur=%.3fs peak=%.2f nan=%s  %s"
          % (rate, len(y) / SR, peak, nan, "OK" if ok else "FAIL"))

sys.exit(1 if failures else 0)
