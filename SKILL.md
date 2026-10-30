---
name: live-tts
description: 让 agent 用语音说话：把回复交给本机 TTS 合成并以正确语速播放到扬声器（默认 Qwen3-TTS / qwentts.cpp，OpenAI 兼容协议，ryan 音色，24 kHz）。当用户说“读出来 / 语音回答 / 说给我听 / 我要练口语 / 开始语音模式 / say it out loud / voice mode”，或要求每条回复都朗读时使用。Make the agent speak its replies through a local TTS engine, with background playback, interruption, voice and rate control.
---

# live-tts

把文字交给本机 TTS，合成 24 kHz 单声道 PCM 并播放。核心脚本是 `say.py`，
默认引擎地址 `http://127.0.0.1:27117`。

## 何时使用

- 用户要求朗读、语音回答、说给我听、开始语音模式。
- 项目规则要求每条面向用户的回复都先朗读。
- 用户要求把一段文字变成音频文件。

## 每轮流程（语音模式）

1. 把**只包含要朗读的正文**写入 UTF-8 文件，例如 `.cache/tts/reply.txt`。
2. 后台朗读：

   ```bash
   python say.py --file .cache/tts/reply.txt --detach
   ```

3. 立刻在界面输出文字回复。代码块、表格、路径、日志不要放进朗读文件。

短句也可以直接传：

```bash
python say.py --text "Nice! What did you order?" --detach
```

## 核心命令

| 命令 | 作用 |
|---|---|
| `python say.py --text "..." --detach` | 后台朗读，立即返回 |
| `python say.py --file reply.txt --detach` | 从文件朗读（推荐） |
| `python say.py --stop` | 停止当前播放 |
| `python say.py --status` | 引擎 / 音色 / 播放状态 |
| `python say.py --doctor` | 提示音 + 朗读一句，排查没声音 |
| `python say.py --no-play --out x.wav` | 只合成，不播放 |

## 声音

- 默认音色 `ryan`；可用 `--voice` 指定，完整列表见 `--list-voices`。
- 默认语速 `1.0`（引擎原生）。用户说“太快 / 慢一点” → `--rate 0.85`；
  “太慢” → `--rate 1.1`。合法范围 0.5~2.0。
- 中英混排会自动切块并分别用对应语言请求。

## 边界

- 不朗读代码块、表格、JSON、链接、文件路径、命令输出、工具日志。
- 纯技术任务默认不朗读；用户说“读出来”再读。
- 用户说“安静 / 别读了” → `python say.py --stop`，之后不再朗读，直到用户说继续。
- 不要用浏览器 `speechSynthesis` 或系统 SAPI 兜底。

## 按需阅读

按顺序读取即可，不需要一次全部加载：

1. 第一次安装、下载引擎和权重：`docs/install.md`
2. 引擎协议 / 换端口 / 换引擎：`docs/engine.md`
3. 完整参数、配置、环境变量、缓存、排障：`docs/reference.md`
4. 让 agent 每轮都朗读、英语陪练人设示例：`docs/voice-mode.md`
5. 可直接粘进项目 `AGENTS.md` 的规则：`examples/AGENTS.snippet.md`
