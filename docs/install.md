# Installation Guide / 安装指南

[English](#english) | [中文](#中文)

<a id="english"></a>
## English

The engine and model weights are **not** stored in Git. Download them from the
[latest release](https://github.com/whodr9726/live-tts/releases/tag/v1.0.0).

### Requirements

- Windows x64
- NVIDIA driver with CUDA 12 runtime (the bundled engine uses CUDA)
- Python 3.8+
- About 3 GB free disk space

### 1. Download

From the release page, download:

| File | Size | SHA256 |
|---|---|---|
| `live-tts-engine-win64-cuda.zip` | 481,874,878 | `5362bf6a66e7c8911cacfead684cfc031915d72a8b2380d4f6bdaeb6bca39d6c` |
| `qwen-talker-1.7b-customvoice-Q8_0.gguf` | 2,042,834,304 | `cab2cff67a0a557310febe558dc83076b28ed790e491867eb2751759f4cd89fa` |
| `qwen-tokenizer-12hz-Q8_0.gguf` | 291,150,624 | `1883beeed99348fc35e23dd225e9082f93f6f8c109330a33d935baa8acdbfd94` |

Also download `SHA256SUMS.txt` and the license files.

### 2. Verify

```powershell
Get-FileHash .\live-tts-engine-win64-cuda.zip -Algorithm SHA256
Get-FileHash .\qwen-talker-1.7b-customvoice-Q8_0.gguf -Algorithm SHA256
Get-FileHash .\qwen-tokenizer-12hz-Q8_0.gguf -Algorithm SHA256
```

Compare each value with `SHA256SUMS.txt` and the table above.

### 3. Install

```powershell
cd <your-live-tts-folder>
New-Item -ItemType Directory -Force .\vendor\tts\models
Expand-Archive .\live-tts-engine-win64-cuda.zip -DestinationPath .\vendor\tts -Force
Move-Item .\qwen-talker-1.7b-customvoice-Q8_0.gguf .\vendor\tts\models\
Move-Item .\qwen-tokenizer-12hz-Q8_0.gguf .\vendor\tts\models\
```

Expected layout:

```text
live-tts/
└─ vendor/tts/
   ├─ tts-server.exe
   ├─ *.dll
   ├─ README-ENGINE.txt
   ├─ LICENSE-*.txt
   ├─ NVIDIA-CUDA-EULA.html
   └─ models/
      ├─ qwen-talker-1.7b-customvoice-Q8_0.gguf
      └─ qwen-tokenizer-12hz-Q8_0.gguf
```

### 4. Check and speak

```powershell
python say.py --status
python say.py --doctor
python say.py --text "Hello! This is my agent speaking." --detach
```

### 5. Install as a skill

Copy the whole folder to a skill directory. `SKILL.md` and `say.py` must stay together.

```text
<project>/.agents/skills/live-tts/      (project-level)
%USERPROFILE%/.agents/skills/live-tts/  (user-level)
```

See [SKILL.md](../SKILL.md) for the agent workflow.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `engine: NOT reachable` | Check that all files were extracted into `vendor/tts/`; install the CUDA 12 runtime; run `python say.py --doctor` |
| Missing DLL | Re-extract the engine zip; do not move individual DLLs out of `vendor/tts/` |
| No sound | Run `say.py --doctor`: no beep means volume/output device; beep but no speech means TTS |
| Port conflict | Change `engine.url` in `config.local.json`, or set `AGENT_TTS_PORT` |
| Slow first start | The engine loads about 2 GB of weights; later starts are faster |

### Privacy

By default `engine.url` is `127.0.0.1`, so text never leaves your machine.
If you change it to a remote address, the text you speak will be sent to that server.

### License

- live-tts code: MIT
- qwentts.cpp and ggml: MIT
- Qwen3-TTS weights: Apache-2.0
- Bundled NVIDIA CUDA runtime libraries: NVIDIA CUDA Toolkit EULA

See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

---

<a id="中文"></a>
## 中文

引擎和模型权重**不在 Git 仓库里**，需要从
[最新 Release](https://github.com/whodr9726/live-tts/releases/tag/v1.0.0) 下载。

### 运行要求

- Windows x64
- 已安装 NVIDIA 驱动和 CUDA 12 运行库（引擎包是 CUDA 构建）
- Python 3.8+
- 约 3 GB 可用磁盘空间

### 第 1 步：下载

在 Release 页面下载这几个文件：

| 文件 | 大小（字节） | SHA256 |
|---|---|---|
| `live-tts-engine-win64-cuda.zip` | 481,874,878 | `5362bf6a66e7c8911cacfead684cfc031915d72a8b2380d4f6bdaeb6bca39d6c` |
| `qwen-talker-1.7b-customvoice-Q8_0.gguf` | 2,042,834,304 | `cab2cff67a0a557310febe558dc83076b28ed790e491867eb2751759f4cd89fa` |
| `qwen-tokenizer-12hz-Q8_0.gguf` | 291,150,624 | `1883beeed99348fc35e23dd225e9082f93f6f8c109330a33d935baa8acdbfd94` |

同时下载 `SHA256SUMS.txt` 和许可证文件。

### 第 2 步：校验文件

在 PowerShell 里执行：

```powershell
Get-FileHash .\live-tts-engine-win64-cuda.zip -Algorithm SHA256
```

```powershell
Get-FileHash .\qwen-talker-1.7b-customvoice-Q8_0.gguf -Algorithm SHA256
```

```powershell
Get-FileHash .\qwen-tokenizer-12hz-Q8_0.gguf -Algorithm SHA256
```

把输出和 `SHA256SUMS.txt`、上面的表格逐一对照。不一致就不要使用。

### 第 3 步：放到项目里

进入 live-tts 仓库目录：

```powershell
cd <your-live-tts-folder>
```

创建目录：

```powershell
New-Item -ItemType Directory -Force .\vendor\tts\models
```

解压引擎包：

```powershell
Expand-Archive .\live-tts-engine-win64-cuda.zip -DestinationPath .\vendor\tts -Force
```

移动两个权重：

```powershell
Move-Item .\qwen-talker-1.7b-customvoice-Q8_0.gguf .\vendor\tts\models\
```

```powershell
Move-Item .\qwen-tokenizer-12hz-Q8_0.gguf .\vendor\tts\models\
```

最终结构必须是：

```text
live-tts/
└─ vendor/tts/
   ├─ tts-server.exe
   ├─ *.dll
   ├─ README-ENGINE.txt
   ├─ LICENSE-*.txt
   ├─ NVIDIA-CUDA-EULA.html
   └─ models/
      ├─ qwen-talker-1.7b-customvoice-Q8_0.gguf
      └─ qwen-tokenizer-12hz-Q8_0.gguf
```

注意：`tts-server.exe` 和所有 DLL 必须在 `vendor/tts/` 根目录，不要拆到子目录；两个 GGUF 必须在 `vendor/tts/models/`。

### 第 4 步：自检

```powershell
python say.py --status
```

看到 `engine : http://127.0.0.1:27117  reachable` 或引擎自动启动成功即可。

```powershell
python say.py --doctor
```

会先响一声，再朗读一句测试。

```powershell
python say.py --text "你好，这是 agent 在说话。" --detach
```

### 第 5 步：作为技能使用

把整个仓库放到 agent 的技能目录。`SKILL.md` 和 `say.py` 必须同级：

| 宿主 | 位置 |
|---|---|
| ZCode / Claude Code（项目级） | `<项目>/.agents/skills/live-tts/` |
| ZCode / Claude Code（用户级） | `%USERPROFILE%\.agents\skills\live-tts\` |
| 其他 CLI agent | 任意目录，直接调用 `python say.py` |

agent 会按 [SKILL.md](../SKILL.md) 的流程先朗读、再输出文字。

### 常见问题

| 现象 | 处理 |
|---|---|
| `engine: NOT reachable` | 确认 `vendor/tts/` 里有 exe 和所有 DLL；确认已安装 CUDA 12 运行库；运行 `python say.py --doctor` |
| 提示缺少 DLL | 重新解压引擎包；不要单独移动 DLL |
| 完全没声音 | `--doctor`：没有提示音 → 检查系统音量和默认输出设备；有提示音但没语音 → 看 TTS 日志 |
| 端口被占用 | 在 `config.local.json` 改 `engine.url`，或设 `AGENT_TTS_PORT` |
| 第一次启动很慢 | 引擎要加载约 2 GB 权重，首次 10~40 秒正常 |
| 想换引擎位置 | 在 `config.local.json` 写绝对路径，见 [engine.md](engine.md) |

### 隐私

默认引擎地址是 `127.0.0.1`，朗读文本不会离开本机。
如果把 `engine.url` 改成远端地址，文本会发送到那台服务器。

### 许可证

- live-tts 代码：MIT
- qwentts.cpp 和 ggml：MIT
- Qwen3-TTS 权重：Apache-2.0
- 随包分发的 NVIDIA CUDA 运行库：NVIDIA CUDA Toolkit EULA

详见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。
