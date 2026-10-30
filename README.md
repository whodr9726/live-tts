# live-tts

[English](#english) | [中文](#chinese)

<a id="english"></a>
## English

> Near-real-time TTS for live translation and AI agents — about 1 second to the first words, 3.5–4× faster than real time, fully local.

**Give your agent a voice that keeps up with the conversation.**

`live-tts` is a local-first text-to-speech skill powered by Qwen3-TTS (qwentts.cpp).
It is built for the last stage of a live translation pipeline: once translated text is
ready, playback starts in about a second, so the voice keeps pace with the speaker
instead of falling seconds behind. No API key, no per-character cost, no waiting for
the whole reply to finish.

### Built for live interpretation

```text
microphone ──► ASR ──► translation ──► live-tts ──► speaker
```

`live-tts` covers the final voice stage. It does **not** do speech recognition or
translation itself; pair it with any ASR and translation layer. The point is latency:
the voice stage should add about a second, not five to ten. End-to-end latency is
ASR + translation + this roughly one-second voice stage.

### Why it feels real-time

- **~1 s to first audio** — short sentence, warm engine, measured on the reference machine.
- **3.5–4× faster than real-time synthesis** — a 5.9 s clip renders in about 1.8 s.
- **Cache hits are instant** — repeated phrases start in under 0.3 s.
- **Interruptible** — a new translated sentence stops the previous one immediately.
- **Never blocks the pipeline** — playback runs in a detached worker; ASR and translation keep flowing.
- **Pitch-preserving speed control** — `--rate 0.85` slows down without lowering the voice.
- **Local and offline** — text never leaves your machine; no API key, no per-character cost.
- **Mixed Chinese/English** — split by script and synthesized separately.
- **Engine-agnostic** — any OpenAI-compatible `POST /v1/audio/speech` returning 24 kHz PCM.

| Scenario | Audio length | Synthesis | First audio |
|---|---|---|---|
| Short sentence, warm engine | 2.9 s | 0.79 s | ~1 s |
| Same sentence, cache hit | 2.9 s | 0.03 s | <0.3 s |
| Medium sentence, warm engine | 4.2 s | 1.03 s | ~1.3 s |
| Longer sentence, warm engine | 5.9 s | 1.75 s | ~1.8 s |

> Measured on the reference machine with a warm engine; hardware and sentence length
> affect these numbers. First run loads about 2 GB of weights (10–40 s), later starts
> are fast. Playback is sentence-level, not token-by-token streaming.

### Where it fits

- **Live translation / simultaneous interpretation** — the voice stage after ASR and MT.
- **Voice agents** — answers that start in about a second, not after the full reply.
- **Language learning** — instant pronunciation playback.
- **Accessibility** — fast screen reading and live captions.
- **Audio previews** — text to speech without a cloud API.

### How it works

```text
agent ──► say.py ──► local TTS engine (default 127.0.0.1:27117) ──► speakers
```

### Quick start

1. Put the engine and weights in `vendor/tts/`. Download them from
   [Releases](../../releases); the step-by-step guide is [docs/install.md](docs/install.md).
   Alternatively, point `config.local.json` at an engine you already have.
2. Check the setup:

   ```bash
   python say.py --status
   ```

3. Speak:

   ```bash
   python say.py --text "Hello! This is my agent speaking." --detach
   ```

### Install as a skill

Copy the repository into a skill directory. `SKILL.md` and `say.py` must stay together.

```bash
git clone <this-repo> ~/.agents/skills/live-tts
python ~/.agents/skills/live-tts/say.py --status
```

The agent then follows [SKILL.md](SKILL.md). To make it speak every reply, use
[examples/AGENTS.snippet.md](examples/AGENTS.snippet.md).

### Documentation

- [SKILL.md](SKILL.md) — skill entry: when to use, per-reply flow, core commands
- [docs/install.md](docs/install.md) — download, verify and install the engine and weights
- [docs/engine.md](docs/engine.md) — engine setup, protocol, ports, weights
- [docs/reference.md](docs/reference.md) — full CLI, config, environment variables, troubleshooting
- [docs/voice-mode.md](docs/voice-mode.md) — "speak every reply" mode and persona example

### Requirements

Python 3.8+; optional `numpy` for pitch-preserving rate changes. qwentts.cpp currently runs
on Windows with CUDA 12. The first run loads about 2 GB of weights (10–40 s); later starts
are fast. Playback is sentence-level, not token streaming; ASR and translation are not
included.

### License

[MIT](LICENSE). Engine binaries and model weights keep their upstream licenses;
see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

<a id="chinese"></a>
## 中文

> 面向实时翻译和 AI agent 的接近实时 TTS——约 1 秒出第一句，合成速度约实时的 3.5～4 倍，完全本地。

**让 agent 的声音跟得上对话。**

`live-tts` 是一个本地优先的 TTS 技能，基于 Qwen3-TTS（qwentts.cpp）。它专为实时翻译
链路的最后一段设计：翻译文字一准备好，约 1 秒后就开始播放，让声音跟得上说话人，而不是
落后好几秒。不需要 API Key，不按字计费，也不用等整段回复生成完。

### 为实时翻译 / 同声传译而生

```text
麦克风 ──► ASR ──► 翻译 ──► live-tts ──► 扬声器
```

`live-tts` 负责最后的语音输出阶段。它**本身不做语音识别和翻译**，需要和 ASR、翻译层配合。
它的价值是延迟：语音阶段只加约 1 秒，而不是 5～10 秒。端到端延迟 = ASR + 翻译 + 约 1 秒
语音阶段。

### 实时感从哪来

- **约 1 秒出第一句**：短句、引擎已热、参考机实测。
- **合成速度约实时的 3.5～4 倍**：5.9 秒音频约 1.8 秒合成完。
- **缓存命中几乎即时**：重复短语 0.3 秒内开始。
- **可打断**：新的翻译句子会立刻停掉上一条。
- **不阻塞链路**：播放跑在独立后台进程，ASR 和翻译可以继续跑。
- **变速不变调**：`--rate 0.85` 放慢语速，不压低音高。
- **本地离线**：文本不出本机，不需要 API Key，没有按字费用。
- **中英混排**：按文字体系切块，分别合成。
- **引擎可替换**：任何返回 24 kHz PCM 的 OpenAI 兼容服务都能接。

| 场景 | 音频时长 | 合成耗时 | 首音延迟 |
|---|---|---|---|
| 短句，引擎已热 | 2.9 秒 | 0.79 秒 | 约 1 秒 |
| 同一句，缓存命中 | 2.9 秒 | 0.03 秒 | 0.3 秒内 |
| 中句，引擎已热 | 4.2 秒 | 1.03 秒 | 约 1.3 秒 |
| 长句，引擎已热 | 5.9 秒 | 1.75 秒 | 约 1.8 秒 |

> 以上为参考机、引擎已热时的实测；不同硬件和句子长度会有差异。首次启动要加载约 2 GB
> 权重（10～40 秒），之后启动很快。播放是句子级，不是逐字流式。

### 适合的场景

- **实时翻译 / 同声传译**：ASR 和机器翻译之后的语音输出层。
- **语音 agent**：回答约 1 秒后开始，而不是等整段生成完。
- **语言学习**：即时播放发音。
- **无障碍**：快速朗读屏幕内容和实时字幕。
- **音频预览**：不依赖云端 API 的文本转语音。

### 工作原理

```text
agent ──► say.py ──► 本机 TTS 引擎（默认 127.0.0.1:27117）──► 扬声器
```

### 快速开始

1. 把引擎和权重放进 `vendor/tts/`。从 [Releases](../../releases) 下载，
   详细步骤见 [docs/install.md](docs/install.md)；也可以用自己的
   `config.local.json` 指向已有引擎。
2. 自检：

   ```bash
   python say.py --status
   ```

3. 说话：

   ```bash
   python say.py --text "你好，这是 agent 在说话。" --detach
   ```

### 作为技能安装

把仓库复制到技能目录，`SKILL.md` 和 `say.py` 必须同级。

```bash
git clone <this-repo> ~/.agents/skills/live-tts
python ~/.agents/skills/live-tts/say.py --status
```

agent 会按 [SKILL.md](SKILL.md) 执行。想让每轮回复都朗读，使用
[examples/AGENTS.snippet.md](examples/AGENTS.snippet.md)。

### 文档

- [SKILL.md](SKILL.md) — 技能入口：何时用、每轮流程、核心命令
- [docs/install.md](docs/install.md) — 下载、校验、安装引擎和权重的详细步骤
- [docs/engine.md](docs/engine.md) — 引擎安装、协议、端口、权重
- [docs/reference.md](docs/reference.md) — 完整命令、配置、环境变量、排障
- [docs/voice-mode.md](docs/voice-mode.md) — “每轮都朗读”模式与人设示例

### 运行要求

Python 3.8+；可选 `numpy` 用于变速不变调。qwentts.cpp 目前运行在 Windows + CUDA 12。
首次启动要加载约 2 GB 权重（10～40 秒），之后启动很快。播放是句子级，不是逐字流式；
不包含语音识别和翻译。

### 许可证

[MIT](LICENSE)。引擎二进制和模型权重遵循各自的上游许可证，详见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
