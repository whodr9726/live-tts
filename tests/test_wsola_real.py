# -*- coding: utf-8 -*-
"""Real-speech rate check: duration must be inversely proportional to --rate.

Run: python tests/test_wsola_real.py
The test synthesizes through the configured engine. When the engine is not
reachable it prints SKIP and exits 0, so it is safe in CI.
"""
import importlib.util
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("saymod", os.path.join(ROOT, "say.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

cfg = m.load_config()
if not m.engine_alive(cfg):
    print("SKIP: TTS engine is not reachable at %s" % m.engine_url(cfg))
    sys.exit(0)

text = "Try saying: I'd like a latte, please. That sounds natural."
pcm = m.synth_pcm(text, cfg.get("voice", "ryan"), "English", cfg)
sr = m.SAMPLE_RATE
base = len(pcm) / 2 / sr
print("raw duration: %.3fs" % base)

failures = 0
for rate in (1.15, 1.0, 0.9, 0.85, 0.7):
    t0 = time.time()
    out = m.stretch(pcm, rate)
    dur = len(out) / 2 / sr
    ratio = dur / base
    ok = abs(ratio - 1.0 / rate) < 0.01
    failures += 0 if ok else 1
    print("rate=%.2f  dur=%.3fs  ratio=%.3f (expect %.3f)  time=%.2fs  %s"
          % (rate, dur, ratio, 1.0 / rate, time.time() - t0, "OK" if ok else "FAIL"))

sys.exit(1 if failures else 0)
