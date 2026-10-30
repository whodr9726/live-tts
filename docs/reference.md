# 参考手册

`say.py` 的完整参数、配置、行为细节与排障。日常使用只需要看 `SKILL.md`；
需要改行为或定位问题时再读这里。

## 1. 命令与参数

```bash
python say.py --text "Hello!"                 # 前台朗读，播完返回
python say.py --text "Hello!" --detach        # 后台朗读，立即返回
python say.py --file reply.txt --detach       # 从 UTF-8 文件朗读
python say.py --stdin --detach                # 从标准输入朗读
python say.py --text "Hi" --no-play --out hi.wav   # 只合成
python say.py --stop                          # 停止当前播放
python say.py --status [--json]               # 状态
python say.py --doctor                        # 自检
python say.py --list-voices                   # 音色列表
```

| 参数 | 说明 |
|---|---|
| `--text TEXT` | 直接传入要朗读的文字 |
| `--file PATH` | 从文件读取；相对路径按当前工作目录解析 |
| `--stdin` | 从标准输入读取（管道） |
| `--voice NAME` | 音色，默认 `ryan`；非内置音色会提示但仍会发给引擎 |
| `--rate FLOAT` | 语速，默认 `1.0`，合法范围 `0.5~2.0`；WSOLA 变速不变调 |
| `--lang English\|Chinese\|auto` | 强制语言；默认 `auto` 按段检测 |
| `--detach` | 后台播放，父进程立即返回 |
| `--no-play` | 只合成，不碰扬声器 |
| `--out PATH` | 额外把合并后的音频写成 WAV（相对路径在启动时转为绝对路径） |
| `--stop` | 停掉正在播放的 worker |
| `--status` | 显示引擎、音色、语速、播放器、缓存 |
| `--json` | 配合 `--status` 输出机器可读 JSON |
| `--doctor` | 状态 + 提示音 + 朗读测试句 |
| `--list-voices` | 打印内置音色 |
| `--no-cache` | 跳过合成缓存 |
| `--version` | 版本号 |

退出码：`0` 正常；`1` 合成或播放失败；`2` 输入为空/无效；`3` 音频设备问题。

## 2. 输入与输出

- 输入三选一：`--text`、`--file`、`--stdin`。都没有且标准输入不是终端时，会读标准输入。
- 文件按 UTF-8（含 BOM）、UTF-8、GB18030 依次尝试解码。
- 每次朗读后：
  - `audio/last.wav`：本次朗读的完整音频副本（仅真正播放时保存）
  - `audio/last.txt`：本次朗读的文本
  - `.cache/tts/say.log`：一行摘要（音色、语速、段数、音频时长、耗时、错误数）
  - `.cache/tts/worker.log`：后台 worker 的输出
  - `.cache/tts/state.json`：当前播放 PID、最近音频时长等
- 合成缓存按 `音色|语言|语速|文本` 的 SHA1 命名，保存在 `.cache/tts/`，
  自动保留最近 400 段。
- `--no-play` 不写 `audio/last.wav`，也不会打断正在播放的语音；配合 `--out` 只产出文件。

## 3. 行为细节

### 分段

- 先清洗 Markdown/emoji，再按 `。！？；…`、`.!?;` 和换行切段。
- 单段超过 `max_chars`（默认 240）会继续按逗号/空格切。
- 过短的段会合并到相邻段（`min_chars` 默认 48）。
- 中英混排按文字体系切块，中文块请求 `language=Chinese`，英文块请求 `English`。
- 总长度超过 `max_total_chars`（默认 6000）会截断。

### 后台播放

- `--detach`：父进程确认引擎可用后，写 payload 并拉起独立 worker，立即返回。
- worker 独立于父进程；终端关掉也会继续播放。
- 新的一次播放会读取 `state.json` 里的 PID，校验是 `say.py` 进程后杀掉它，
  实现“新回复打断旧回复”。
- `--stop` 做同样的事，然后清空 PID。

### 变速

- 引擎忽略 `speed` 参数，变速在客户端做。
- `rate != 1.0` 时使用 WSOLA，保持音高；没有 numpy 时退化为线性重采样（音高会变）。
- 实测 rate 0.7~1.15 时，时长与 `1/rate` 的误差小于 1%。

### 引擎

- 默认 `http://127.0.0.1:27117`，通过 `POST /v1/audio/speech` 合成。
- 引擎未监听且 `engine.autostart` 为真时，按 `engine.exe` 冷启动。
- 首次加载权重约 10~40 秒；之后是热启动。
- 详见 [engine.md](engine.md)。

## 4. 配置

```text
config.json          默认值（随仓库分发）
config.local.json    个人覆盖（已 gitignore，不参与分发）
环境变量              优先级最高
```

两个 JSON 做深合并；配置里的相对路径以**技能目录**（`say.py` 所在目录）为基准。

| 键 | 默认 | 说明 |
|---|---|---|
| `voice` | `ryan` | 默认音色 |
| `rate` | `1.0` | 默认语速 |
| `language` | `auto` | `auto` / `English` / `Chinese` |
| `engine.url` | `http://127.0.0.1:27117` | 引擎地址 |
| `engine.autostart` | `true` | 引擎未监听时是否冷启动 |
| `engine.exe` | `vendor/tts/tts-server.exe` | 引擎可执行文件 |
| `engine.model` | `vendor/tts/models/qwen-talker-...gguf` | talker 权重 |
| `engine.codec` | `vendor/tts/models/qwen-tokenizer-...gguf` | tokenizer 权重 |
| `engine.boot_timeout_s` | `120` | 冷启动等待秒数 |
| `engine.extra_args` | `[]` | 追加给引擎的命令行参数 |
| `cache_dir` | `.cache/tts` | 合成缓存与日志 |
| `audio_dir` | `audio` | 最近一次朗读副本 |
| `max_chars` | `240` | 单段最大字符数 |
| `min_chars` | `48` | 过短段的合并阈值 |
| `max_total_chars` | `6000` | 单次朗读总长度上限 |

环境变量：

| 变量 | 作用 |
|---|---|
| `AGENT_TTS_URL` | 引擎地址 |
| `AGENT_TTS_PORT` | 重写为本机端口（生成 `http://127.0.0.1:<port>`） |
| `AGENT_TTS_EXE` / `AGENT_TTS_MODEL` / `AGENT_TTS_CODEC` | 引擎文件路径 |
| `AGENT_TTS_AUTOSTART` | `0/false` 关闭冷启动 |
| `AGENT_TTS_VOICE` / `AGENT_TTS_RATE` | 默认音色 / 语速 |
| `AGENT_TTS_CACHE` / `AGENT_TTS_AUDIO` | 缓存目录 / 音频副本目录 |

## 5. 排障

| 现象 | 处理 |
|---|---|
| 完全没声音 | `python say.py --doctor`：有提示音 → 设备正常，问题在 TTS；没提示音 → 音量/输出设备 |
| 引擎没起 | `--status`；失败时检查 `engine.exe` 与两个 `.gguf` 是否存在 |
| 只有部分句子有声 | 看 `.cache/tts/say.log`、`.cache/tts/worker.log` 里的 `errs=` |
| 朗读变成上一条 | 新朗读会打断旧朗读；这是设计行为 |
| 后台没开始 | 看 `.cache/tts/worker.log`；确认 `python` 在 PATH |
| 语速不对 | 确认端口没被其他程序占用；确认按 24 kHz 播放（脚本已处理） |
| 声音像机器人 | 确认没有别的程序同时占用该端口，也没有走浏览器合成 |
| 播放停不下来 | 再执行 `--stop`；仍不行就在任务管理器结束对应的 `python` worker |

## 6. 跨平台

| 平台 | 播放方式 |
|---|---|
| Windows | `winsound.PlaySound`（同步） |
| macOS | `afplay` |
| Linux | `paplay` / `aplay` / `ffplay`（依次尝试） |

后台模式：Windows 用 detached process，POSIX 用新会话。
停止播放：Windows 用 `tasklist` + `taskkill`，POSIX 校验 `say.py` 进程后发 `SIGTERM`。

## 7. 隐私

- 默认只连 `127.0.0.1`，文本不出本机。
- 如果把 `engine.url` 改成远端地址，朗读文本会发送到那台服务器。
- `.cache/tts/` 存的是合成后的 WAV（文件名是哈希）和日志；`audio/last.txt` 存最近一次朗读文本。
  对隐私敏感时，定期删除这两个目录。
