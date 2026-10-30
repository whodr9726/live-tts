#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""say.py — make an agent speak through a local TTS engine.

Default engine: qwentts.cpp / Qwen3-TTS (OpenAI-compatible), voice `ryan`.
Protocol: POST {engine.url}/v1/audio/speech
    {"input": "...", "voice": "ryan", "language": "English", "response_format": "pcm"}
Response: 24000 Hz / s16le / mono PCM. Playback must interpret it as 24 kHz,
otherwise the speaking rate is wrong.

The engine ignores the OpenAI `speed` field, so this script does client-side
WSOLA time-stretching (pitch preserved) whenever --rate != 1.0.

Usage:
    python say.py --text "Hello there!"              foreground, returns after playback
    python say.py --file reply.txt --detach          background, returns immediately
    python say.py --stdin --detach                   pipe text in
    python say.py --text "Hi" --no-play --out hi.wav synthesize only, no playback
    python say.py --stop                             stop the current playback
    python say.py --status [--json]                  engine / config / cache status
    python say.py --doctor                           beep + test sentence
    python say.py --list-voices                      show built-in voice names

Exit codes: 0 ok, 1 synthesis or playback failure, 2 bad input, 3 audio device issue.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import wave

VERSION = "1.0.0"

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")
LOCAL_CONFIG_PATH = os.path.join(SKILL_DIR, "config.local.json")

SAMPLE_RATE = 24000  # engine output; must be used for the WAV header and stretching

# Voices shipped with the Qwen3-TTS custom-voice model. Other engines may
# accept different names; say.py only warns, it does not block them.
KNOWN_VOICES = ["ryan", "serena", "vivian", "uncle_fu", "aiden",
                "ono_anna", "sohee", "eric", "dylan"]

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u2B00-\u2BFF]")
LATIN_RE = re.compile(r"[A-Za-z]")

DEFAULT_CONFIG = {
    "voice": "ryan",
    "rate": 1.0,
    "language": "auto",
    "engine": {
        "url": "http://127.0.0.1:27117",
        "autostart": True,
        "exe": "vendor/tts/tts-server.exe",
        "model": "vendor/tts/models/qwen-talker-1.7b-customvoice-Q8_0.gguf",
        "codec": "vendor/tts/models/qwen-tokenizer-12hz-Q8_0.gguf",
        "boot_timeout_s": 120,
        "extra_args": [],
    },
    "cache_dir": ".cache/tts",
    "audio_dir": "audio",
    "max_chars": 240,
    "min_chars": 48,
    "max_total_chars": 6000,
}


# ---------------------------------------------------------------- basics

def out(*args):
    print(*args, flush=True)


def _deep_merge(base, override):
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _env(name):
    v = os.environ.get(name)
    return v if v else None


def _apply_env(cfg):
    """Environment overrides win over config files (handy for CI / other agents)."""
    eng = cfg["engine"]
    if _env("AGENT_TTS_URL"):
        eng["url"] = _env("AGENT_TTS_URL")
    if _env("AGENT_TTS_PORT"):
        eng["url"] = "http://127.0.0.1:%d" % int(_env("AGENT_TTS_PORT"))
    if _env("AGENT_TTS_EXE"):
        eng["exe"] = _env("AGENT_TTS_EXE")
    if _env("AGENT_TTS_MODEL"):
        eng["model"] = _env("AGENT_TTS_MODEL")
    if _env("AGENT_TTS_CODEC"):
        eng["codec"] = _env("AGENT_TTS_CODEC")
    if _env("AGENT_TTS_AUTOSTART"):
        eng["autostart"] = _env("AGENT_TTS_AUTOSTART").lower() in ("1", "true", "yes", "on")
    if _env("AGENT_TTS_VOICE"):
        cfg["voice"] = _env("AGENT_TTS_VOICE")
    if _env("AGENT_TTS_RATE"):
        cfg["rate"] = float(_env("AGENT_TTS_RATE"))
    if _env("AGENT_TTS_CACHE"):
        cfg["cache_dir"] = _env("AGENT_TTS_CACHE")
    if _env("AGENT_TTS_AUDIO"):
        cfg["audio_dir"] = _env("AGENT_TTS_AUDIO")


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    for path in (CONFIG_PATH, LOCAL_CONFIG_PATH):
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8-sig") as f:
                    _deep_merge(cfg, json.load(f))
            except Exception as e:
                out("[config] cannot read %s: %s" % (path, e))
    _apply_env(cfg)
    return cfg


def _resolve(p):
    p = os.path.expanduser(str(p))
    if not os.path.isabs(p):
        p = os.path.join(SKILL_DIR, p)
    return os.path.normpath(p)


def cache_dir(cfg):
    d = _resolve(cfg.get("cache_dir") or ".cache/tts")
    os.makedirs(d, exist_ok=True)
    return d


def audio_dir(cfg):
    d = _resolve(cfg.get("audio_dir") or "audio")
    os.makedirs(d, exist_ok=True)
    return d


def port_open(port, timeout=0.35):
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except Exception:
        return False


# ---------------------------------------------------------------- engine

def engine_url(cfg):
    eng = cfg["engine"]
    url = str(eng.get("url") or "").strip()
    if not url:
        url = "http://127.0.0.1:%d" % int(eng.get("port", 27117))
    return url.rstrip("/")


def _url_host_port(url):
    from urllib.parse import urlparse
    u = urlparse(url)
    host = u.hostname or "127.0.0.1"
    port = u.port or (443 if u.scheme == "https" else 80)
    return host, int(port)


def engine_is_local(cfg):
    host, _ = _url_host_port(engine_url(cfg))
    return host in ("127.0.0.1", "localhost", "::1", "0.0.0.0")


def _http_get_json(url, timeout=3):
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def engine_alive(cfg):
    return _http_get_json(engine_url(cfg) + "/v1/models", timeout=3) is not None


def _discover_model_paths(cfg):
    """Use configured paths; if only exe is missing, look for GGUF files next to the model."""
    eng = cfg["engine"]
    exe = _resolve(eng["exe"])
    model = _resolve(eng["model"])
    codec = _resolve(eng["codec"])
    if os.path.isfile(exe) and os.path.isfile(model) and os.path.isfile(codec):
        return exe, model, codec
    model_dir = os.path.dirname(model)
    if os.path.isdir(model_dir):
        ggufs = [os.path.join(model_dir, f) for f in os.listdir(model_dir)
                 if f.lower().endswith(".gguf")]
        talker = next((p for p in ggufs if "customvoice" in os.path.basename(p).lower()), None)
        codec2 = next((p for p in ggufs if "tokenizer" in os.path.basename(p).lower()), None)
        if talker and codec2:
            return exe, talker, codec2
    return exe, model, codec


def ensure_engine(cfg, quiet=False):
    """Start the local engine when it is down. Returns True when reachable."""
    if engine_alive(cfg):
        return True

    url = engine_url(cfg)
    if not engine_is_local(cfg):
        if not quiet:
            out("[engine] %s is not reachable (remote engine: autostart skipped)" % url)
        return False

    eng = cfg["engine"]
    if not eng.get("autostart", True):
        if not quiet:
            out("[engine] %s is not reachable and autostart is disabled" % url)
        return False

    exe, model, codec = _discover_model_paths(cfg)
    if not (os.path.isfile(exe) and os.path.isfile(model) and os.path.isfile(codec)):
        out("[engine] cannot start: engine binary or model files are missing\n"
            "         exe   = %s (%s)\n         model = %s (%s)\n         codec = %s (%s)\n"
            "         Put the engine in vendor/tts/ or set engine paths in config.local.json."
            % (exe, os.path.isfile(exe), model, os.path.isfile(model),
               codec, os.path.isfile(codec)))
        return False

    out("[engine] %s is down, cold-starting the TTS engine... (%s)" % (url, exe))
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW

    exe_dir = os.path.dirname(exe)
    # The engine parses argv as ANSI on Windows. Passing an absolute path that
    # contains non-ASCII characters (e.g. a Chinese project directory) turns
    # into mojibake, so start from the engine directory with relative paths.
    try:
        model_arg = os.path.relpath(model, exe_dir)
        codec_arg = os.path.relpath(codec, exe_dir)
    except ValueError:
        model_arg, codec_arg = model, codec
    if os.name == "nt" and not model_arg.isascii():
        model_arg, codec_arg = model, codec

    cmd = [exe, "--model", model_arg, "--codec", codec_arg,
           "--port", str(_url_host_port(url)[1])]
    cmd.extend(str(a) for a in (eng.get("extra_args") or []))
    try:
        subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=creationflags,
            close_fds=True, cwd=exe_dir)
    except Exception as e:
        out("[engine] failed to start: %s" % e)
        return False

    t0 = time.time()
    deadline = t0 + float(eng.get("boot_timeout_s", 120))
    while time.time() < deadline:
        if engine_alive(cfg):
            out("[engine] ready (%.1fs)" % (time.time() - t0))
            return True
        time.sleep(0.5)
    out("[engine] timed out after %ss" % eng.get("boot_timeout_s", 120))
    return False


def synth_pcm(text, voice, lang, cfg, timeout=180):
    """POST /v1/audio/speech -> 24 kHz s16le mono PCM bytes."""
    import urllib.request
    body = json.dumps({
        "input": text,
        "voice": voice,
        "language": lang,
        "response_format": "pcm",
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        engine_url(cfg) + "/v1/audio/speech", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = (r.headers.get("Content-Type") or "").lower()
        data = r.read()
    if "audio" not in ctype and "octet-stream" not in ctype:
        raise RuntimeError("engine returned non-audio (%s): %s"
                           % (ctype, data[:200].decode("utf-8", "replace")))
    if len(data) < 2:
        raise RuntimeError("engine returned empty audio")
    return data[: len(data) - (len(data) % 2)]


# ---------------------------------------------------------------- rate (WSOLA)

def _stretch_linear(pcm, rate):
    """Fallback without numpy: linear resampling (pitch shifts slightly)."""
    import array
    a = array.array("h")
    a.frombytes(pcm)
    n_in = len(a)
    n_out = max(1, int(round(n_in / rate)))
    res = array.array("h", bytes(2 * n_out))
    for i in range(n_out):
        x = i * rate
        i0 = int(x)
        i1 = min(i0 + 1, n_in - 1)
        frac = x - i0
        res[i] = int(a[i0] * (1 - frac) + a[i1] * frac)
    return res.tobytes()


def stretch(pcm, rate):
    """Scale duration by `rate` (rate<1 slower, >1 faster) while keeping pitch."""
    if abs(rate - 1.0) < 0.005:
        return pcm
    try:
        import numpy as np
    except Exception:
        return _stretch_linear(pcm, rate)

    x = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    n = len(x)
    if n < 4096:
        return _stretch_linear(pcm, rate)

    frame = 960                      # 40 ms @ 24 kHz
    hop_s = frame // 4               # 10 ms synthesis hop (75% overlap)
    hop_a = max(1, int(round(hop_s * rate)))
    tmpl = 192                       # 8 ms alignment template
    search = 96                      # +-4 ms search
    win = np.hanning(frame).astype(np.float32)

    n_out = int(round(n / rate)) + frame
    y = np.zeros(n_out, np.float32)
    w = np.zeros(n_out, np.float32)

    pos = 0
    o = 0
    while o + frame <= n_out and pos + frame <= n:
        y[o:o + frame] += x[pos:pos + frame] * win
        w[o:o + frame] += win
        o += hop_s

        expected = pos + hop_a
        if pos + hop_s + tmpl <= n:
            template = x[pos + hop_s:pos + hop_s + tmpl]
            lo = max(0, expected - search)
            hi = min(n - tmpl, expected + search)
            if hi > lo:
                corr = np.correlate(x[lo:hi + tmpl], template, mode="valid")
                pos = lo + int(np.argmax(corr))
            else:
                pos = expected
        else:
            pos = expected
        pos = min(pos, n - frame)
        if pos < 0:
            break

    w[w < 1e-3] = 1.0
    y = np.clip(y / w, -1.0, 1.0)
    target = max(1, int(round(n / rate)))
    if len(y) > target:
        y = y[:target]
    return (y * 32767.0).astype("<i2").tobytes()


def pcm_to_wav(pcm, path):
    tmp = path + ".tmp%d" % os.getpid()
    with wave.open(tmp, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm)
    os.replace(tmp, path)


# ---------------------------------------------------------------- text

def clean_text(text):
    t = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = EMOJI_RE.sub(" ", t)
    t = re.sub(r"[*_~#>|^]+", " ", t)
    t = re.sub(r"[ \t\f\v]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def language_of(text, cfg):
    forced = (cfg.get("language") or "auto").lower()
    if forced in ("english", "chinese"):
        return "Chinese" if forced == "chinese" else "English"
    cjk = len(CJK_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    if cjk and latin:
        return "Chinese" if cjk * 3 >= latin else "English"
    return "Chinese" if cjk else "English"


def _split_runs(text):
    """Split mixed Chinese/English into runs, each requested with its own language."""
    if not (CJK_RE.search(text) and LATIN_RE.search(text)):
        return [text]
    runs = re.findall(r"[\u4e00-\u9fff][\u4e00-\u9fff，。！？、；：\"'（）《》\s]*"
                      r"|[^\u4e00-\u9fff]+", text)
    return [r.strip() for r in runs if r.strip()]


def split_segments(text, cfg):
    max_chars = int(cfg.get("max_chars", 240))
    min_chars = int(cfg.get("min_chars", 48))
    raw = re.split(r"(?<=[.!?。！？；;…])\s*|\n+", text)

    parts = []
    for piece in raw:
        p = piece.strip()
        if not p:
            continue
        while len(p) > max_chars:
            cut = max(p.rfind("，", 0, max_chars), p.rfind(",", 0, max_chars),
                      p.rfind("；", 0, max_chars), p.rfind("、", 0, max_chars))
            if cut < max_chars * 0.4:
                cut = p.rfind(" ", 0, max_chars)
            if cut < max_chars * 0.4:
                cut = max_chars - 1
            parts.append(p[:cut + 1].strip())
            p = p[cut + 1:].strip()
        if p:
            parts.append(p)

    merged = []
    buf = ""
    for p in parts:
        if buf and len(buf) + len(p) + 1 > max_chars:
            merged.append(buf)
            buf = p
        elif len(p) < min_chars:
            buf = (buf + " " + p).strip() if buf else p
        else:
            if buf:
                merged.append(buf)
                buf = ""
            merged.append(p)
    if buf:
        merged.append(buf)

    segs = []
    for s in merged:
        for run in _split_runs(s):
            segs.append({"text": run, "lang": language_of(run, cfg)})
    return segs


# ---------------------------------------------------------------- cache & state

def _cache_key(text, voice, lang, rate):
    h = hashlib.sha1()
    h.update(("%s|%s|%.3f|%s" % (voice, lang, rate, text)).encode("utf-8"))
    return h.hexdigest()[:20]


def render_segment(text, voice, lang, rate, cfg, use_cache=True):
    """Return a WAV path ready to play (cache hit returns immediately)."""
    cdir = cache_dir(cfg)
    key = _cache_key(text, voice, lang, rate)
    wav_path = os.path.join(cdir, key + ".wav")
    if use_cache and os.path.isfile(wav_path):
        return wav_path
    pcm = synth_pcm(text, voice, lang, cfg)
    if abs(rate - 1.0) >= 0.005:
        pcm = stretch(pcm, rate)
    pcm_to_wav(pcm, wav_path)
    return wav_path


def prune_cache(cfg, limit=400):
    cdir = cache_dir(cfg)
    try:
        wavs = [os.path.join(cdir, f) for f in os.listdir(cdir) if f.endswith(".wav")]
        if len(wavs) > limit:
            wavs.sort(key=lambda p: os.path.getmtime(p))
            for p in wavs[: len(wavs) - limit]:
                try:
                    os.remove(p)
                except OSError:
                    pass
        payloads = [os.path.join(cdir, f) for f in os.listdir(cdir)
                    if f.startswith("payload-") and f.endswith(".json")]
        if len(payloads) > 30:
            payloads.sort(key=lambda p: os.path.getmtime(p))
            for p in payloads[: len(payloads) - 30]:
                try:
                    os.remove(p)
                except OSError:
                    pass
    except Exception:
        pass


def state_path(cfg):
    return os.path.join(cache_dir(cfg), "state.json")


def read_state(cfg):
    try:
        with open(state_path(cfg), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_state(cfg, **kw):
    st = read_state(cfg)
    st.update(kw)
    st["updated"] = time.time()
    try:
        tmp = state_path(cfg) + ".tmp%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
        os.replace(tmp, state_path(cfg))
    except Exception:
        pass


def _proc_image(pid):
    """Process image name, used to avoid killing an unrelated process on PID reuse."""
    try:
        if os.name == "nt":
            r = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"],
                               capture_output=True, text=True, errors="replace", timeout=8)
            lines = (r.stdout or "").strip().splitlines()
            if not lines or "No tasks" in lines[0] or lines[0].startswith("INFO"):
                return ""
            return lines[0].split(",")[0].strip('"').lower()
        r = subprocess.run(["ps", "-p", str(pid), "-o", "comm="],
                           capture_output=True, text=True, timeout=8)
        return (r.stdout or "").strip().lower()
    except Exception:
        return ""


def _proc_is_player(pid):
    if os.name == "nt":
        return "python" in _proc_image(pid)
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/%d/cmdline" % pid, "rb") as f:
                cmd = f.read().replace(b"\x00", b" ").decode("utf-8", "replace")
        else:
            r = subprocess.run(["ps", "-p", str(pid), "-o", "command="],
                               capture_output=True, text=True, timeout=8)
            cmd = r.stdout or ""
        return "say.py" in cmd
    except Exception:
        return False


def stop_playback(cfg, announce=False):
    st = read_state(cfg)
    pid = st.get("pid")
    killed = False
    if pid and _proc_is_player(int(pid)):
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/PID", str(int(pid))],
                               capture_output=True, timeout=8)
            else:
                os.kill(int(pid), signal.SIGTERM)
            killed = True
        except Exception:
            pass
    write_state(cfg, pid=None)
    if announce:
        out("[say] stopped the current playback" if killed else "[say] nothing is playing")
    return killed


# ---------------------------------------------------------------- playback

def play_wav(path):
    if os.name == "nt":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_SYNC
                           | winsound.SND_NODEFAULT)
        return
    if sys.platform == "darwin":
        subprocess.run(["afplay", path], check=True)
        return
    for cmd in (["paplay", path], ["aplay", "-q", path],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, check=True)
            return
    raise RuntimeError("no audio player found (install paplay, aplay or ffplay)")


def _wav_pcm(path):
    with wave.open(path, "rb") as f:
        return f.readframes(f.getnframes())


def combine_wavs(paths, out_path, gap_ms=70):
    gap = b"\x00\x00" * int(SAMPLE_RATE * gap_ms / 1000)
    chunks = []
    for i, p in enumerate(paths):
        if i:
            chunks.append(gap)
        chunks.append(_wav_pcm(p))
    pcm_to_wav(b"".join(chunks), out_path)


# ---------------------------------------------------------------- execution

def run_playback(segments, voice, rate, cfg, save_audio=True, play=True, out_path=None):
    if not segments:
        out("[say] nothing to speak")
        return 2

    if play:
        stop_playback(cfg)                  # a new reply interrupts the previous one
        write_state(cfg, pid=os.getpid(), started=time.time(), voice=voice, rate=rate)

    cdir = cache_dir(cfg)
    use_cache = bool(cfg.get("_use_cache", True))
    errs = []
    rendered = []
    t0 = time.time()

    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        futures = [pool.submit(render_segment, seg["text"], voice, seg["lang"],
                               rate, cfg, use_cache) for seg in segments]
        for i, fut in enumerate(futures):
            try:
                wav_path = fut.result()
            except Exception as e:
                errs.append("segment %d synthesis failed: %s" % (i + 1, e))
                out("[say] segment %d synthesis failed: %s" % (i + 1, e))
                continue
            rendered.append(wav_path)
            if play:
                try:
                    play_wav(wav_path)
                except Exception as e:
                    errs.append("playback failed: %s" % e)
                    out("[say] playback failed: %s" % e)
                    break
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    if save_audio and play and rendered:
        try:
            adir = audio_dir(cfg)
            combine_wavs(rendered, os.path.join(adir, "last.wav"))
            with open(os.path.join(adir, "last.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(s["text"] for s in segments))
        except Exception as e:
            out("[say] failed to save the last-audio copy: %s" % e)

    if out_path and rendered:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            combine_wavs(rendered, out_path)
            out("[say] wrote %s" % out_path)
        except Exception as e:
            errs.append("writing %s failed: %s" % (out_path, e))
            out("[say] writing %s failed: %s" % (out_path, e))

    total = sum(len(_wav_pcm(p)) / 2 for p in rendered) / float(SAMPLE_RATE) if rendered else 0.0
    dur = time.time() - t0
    log_line = ("%s voice=%s rate=%.2f segs=%d audio=%.2fs wall=%.2fs%s"
                % (time.strftime("%Y-%m-%d %H:%M:%S"), voice, rate, len(rendered),
                   total, dur, (" errs=%d" % len(errs)) if errs else ""))
    try:
        with open(os.path.join(cdir, "say.log"), "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception:
        pass
    out("[say] %s" % log_line)
    write_state(cfg, last_audio_sec=round(total, 2))
    if play:
        write_state(cfg, pid=None)
    prune_cache(cfg)
    return 0 if not errs else 1


def build_segments(text, cfg):
    cleaned = clean_text(text)
    if not cleaned:
        return []
    cap = int(cfg.get("max_total_chars", 6000))
    if len(cleaned) > cap:
        cleaned = cleaned[:cap]
        out("[say] text too long, truncated to %d characters" % cap)
    return split_segments(cleaned, cfg)


def _decode_bytes(raw):
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def read_text_input(args):
    if args.text:
        return args.text
    if args.file:
        p = args.file
        if not os.path.isabs(p):
            p = os.path.join(os.getcwd(), p)
        if not os.path.isfile(p):
            out("[say] text file not found: %s" % p)
            return ""
        with open(p, "rb") as f:
            return _decode_bytes(f.read())
    if args.stdin or not sys.stdin.isatty():
        # Read bytes: Windows consoles decode piped stdin as GBK by default.
        return _decode_bytes(sys.stdin.buffer.read())
    return ""


def estimate_seconds(segments):
    chars = sum(len(s["text"]) for s in segments)
    cjk = sum(len(CJK_RE.findall(s["text"])) for s in segments)
    latin = max(0, chars - cjk)
    return cjk / 5.0 + latin / 14.0


def cmd_status(cfg, as_json=False):
    url = engine_url(cfg)
    listening = engine_alive(cfg)
    model_id = ""
    if listening:
        models = _http_get_json(url + "/v1/models", timeout=3)
        if models and models.get("data"):
            model_id = models["data"][0].get("id", "")
    st = read_state(cfg)
    pid = st.get("pid")
    alive = bool(pid) and _proc_is_player(int(pid))
    cdir = cache_dir(cfg)
    n_cache = len([f for f in os.listdir(cdir) if f.endswith(".wav")]) if os.path.isdir(cdir) else 0

    info = {
        "version": VERSION,
        "engine": {
            "url": url,
            "reachable": listening,
            "local": engine_is_local(cfg),
            "model": model_id,
        },
        "voice": cfg.get("voice"),
        "rate": float(cfg.get("rate", 1.0)),
        "language": cfg.get("language"),
        "player": {"pid": pid if alive else None, "playing": alive},
        "cache": {"dir": cdir, "wavs": n_cache},
        "audio_dir": audio_dir(cfg),
    }
    if as_json:
        out(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    out("engine : %s  %s%s" % (url, "reachable" if listening else "NOT reachable",
                               ("  model " + model_id) if model_id else ""))
    out("voice  : %s   rate: %.2f   language: %s"
        % (cfg.get("voice"), float(cfg.get("rate", 1.0)), cfg.get("language")))
    out("player : %s" % (("playing pid=%s" % pid) if alive else "idle"))
    out("cache  : %s (%d segments)" % (cdir, n_cache))
    return 0


def cmd_doctor(cfg):
    cmd_status(cfg)
    out("")
    ok = ensure_engine(cfg)
    out("[1/3] engine: %s" % ("ok" if ok else "unavailable"))
    if not ok:
        return 1
    try:
        if os.name == "nt":
            import winsound
            winsound.Beep(880, 260)
            out("[2/3] beep played (880 Hz, 260 ms) - no sound means volume/device issue")
        else:
            print("\a", end="", flush=True)
            out("[2/3] terminal bell sent (no system beep on this platform)")
    except Exception as e:
        out("[2/3] beep failed: %s" % e)
        return 3
    segs = [{"text": "Voice check. One, two, three. This is Ryan speaking.",
             "lang": "English"}]
    rc = run_playback(segs, cfg.get("voice", "ryan"), float(cfg.get("rate", 1.0)),
                      cfg, save_audio=True)
    out("[3/3] speech test: %s   copy: %s"
        % ("ok" if rc == 0 else "failed", os.path.join(audio_dir(cfg), "last.wav")))
    return rc


# ---------------------------------------------------------------- background worker

def spawn_worker(payload_path, cfg):
    cdir = cache_dir(cfg)
    log_path = os.path.join(cdir, "worker.log")
    flags = 0
    kwargs = {}
    if os.name == "nt":
        flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        kwargs["start_new_session"] = True
    log = open(log_path, "ab")
    try:
        p = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--worker", payload_path],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            creationflags=flags, close_fds=True, cwd=SKILL_DIR, **kwargs)
    finally:
        log.close()
    return p.pid


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(
        description="Speak text through a local TTS engine (24 kHz PCM).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python say.py --text \"Hello there!\"\n"
               "  python say.py --file reply.txt --detach\n"
               "  python say.py --text \"Hi\" --no-play --out hi.wav\n"
               "  python say.py --stop\n"
               "  python say.py --status --json\n")
    ap.add_argument("--text")
    ap.add_argument("--file")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--voice", default=None)
    ap.add_argument("--rate", type=float, default=None)
    ap.add_argument("--lang", default=None, help="English / Chinese / auto")
    ap.add_argument("--detach", action="store_true", help="play in the background, return immediately")
    ap.add_argument("--no-play", action="store_true", help="synthesize only, do not touch the speakers")
    ap.add_argument("--out", default=None, help="also write the combined audio to this WAV path")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--doctor", action="store_true")
    ap.add_argument("--json", action="store_true", help="machine-readable output for --status")
    ap.add_argument("--list-voices", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--version", action="version", version="live-tts " + VERSION)
    ap.add_argument("--worker", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    cfg = load_config()
    if args.lang:
        cfg["language"] = args.lang
    voice = args.voice or cfg.get("voice", "ryan")
    if voice not in KNOWN_VOICES:
        out("[say] note: %r is not a built-in voice; passing it to the engine anyway" % voice)
    rate = float(args.rate if args.rate is not None else cfg.get("rate", 1.0))
    if not (0.5 <= rate <= 2.0):
        out("[say] rate out of range 0.5-2.0, using 1.0")
        rate = 1.0
    cfg["_use_cache"] = not args.no_cache

    if args.list_voices:
        out(" ".join(KNOWN_VOICES))
        return 0
    if args.stop:
        stop_playback(cfg, announce=True)
        return 0
    if args.status:
        return cmd_status(cfg, as_json=args.json)
    if args.doctor:
        return cmd_doctor(cfg)

    if args.worker:
        with open(args.worker, encoding="utf-8") as f:
            payload = json.load(f)
        cfg["_use_cache"] = payload.get("use_cache", True)
        return run_playback(payload["segments"], payload["voice"],
                            payload["rate"], cfg,
                            save_audio=payload.get("save_audio", True),
                            play=payload.get("play", True),
                            out_path=payload.get("out_path"))

    text = read_text_input(args)
    if not text.strip():
        out("[say] no input text (use --text, --file or --stdin)")
        return 2
    segments = build_segments(text, cfg)
    if not segments:
        out("[say] nothing to speak after cleaning the text")
        return 2

    out_path = os.path.abspath(args.out) if args.out else None

    if args.detach:
        if not ensure_engine(cfg):
            return 1
        if not args.no_play:
            stop_playback(cfg)
        cdir = cache_dir(cfg)
        payload_path = os.path.join(cdir, "payload-%d.json" % int(time.time() * 1000))
        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump({"segments": segments, "voice": voice, "rate": rate,
                       "use_cache": cfg["_use_cache"], "save_audio": True,
                       "play": not args.no_play, "out_path": out_path},
                      f, ensure_ascii=False)
        pid = spawn_worker(payload_path, cfg)
        out("[say] background playback started pid=%d, %d segments, ~%.1fs audio"
            % (pid, len(segments), estimate_seconds(segments)))
        return 0

    if not ensure_engine(cfg):
        return 1
    return run_playback(segments, voice, rate, cfg,
                        save_audio=True, play=not args.no_play,
                        out_path=out_path)


if __name__ == "__main__":
    sys.exit(main())
