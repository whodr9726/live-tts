# 引擎部署与协议

> 第一次安装（下载 Release 资产、校验 SHA256、放置目录）请看 [install.md](install.md)。
> 本文件讲协议、端口、冷启动和换引擎。

`say.py` 不绑定某一个可执行文件：只要服务满足下面的协议，就能说话。
默认配置针对 **qwentts.cpp / Qwen3-TTS**（本机副本，端口 27117）。

## 1. HTTP 协议

```
POST http://127.0.0.1:27117/v1/audio/speech
Content-Type: application/json

{
  "input": "Hello, let's practice.",
  "voice": "ryan",
  "language": "English",
  "response_format": "pcm"
}
```

响应：流式或一次性二进制 **PCM，s16le / 24000 Hz / 单声道**。

- **必须按 24 kHz 解释**，否则语速一定错（本脚本已固定 24 kHz）。
- 引擎**忽略** `speed`；变速由 `say.py` 在客户端用 WSOLA 完成。
- `language` 取 `English` 或 `Chinese`；中英混排时 `say.py` 会按文字体系切块分别请求，
  因为引擎跨语种容易串味。
- 探测接口：`GET /v1/models`，返回 OpenAI 风格的模型列表。`say.py` 用它判断引擎是否就绪。

内置音色（customvoice 模型）：

```
ryan  serena  vivian  uncle_fu  aiden  ono_anna  sohee  eric  dylan
```

## 2. 目录布局

推荐把引擎放进技能目录，形成自包含结构：

```
live-tts/
└─ vendor/tts/
   ├─ tts-server.exe
   ├─ ggml.dll
   ├─ ggml-base.dll
   ├─ ggml-cpu.dll
   ├─ ggml-cuda.dll
   ├─ cudart64_12.dll
   ├─ cublas64_12.dll
   ├─ cublasLt64_12.dll
   └─ models/
      ├─ qwen-talker-1.7b-customvoice-Q8_0.gguf
      └─ qwen-tokenizer-12hz-Q8_0.gguf
```

- 对应 `config.json` 的 `engine.exe / engine.model / engine.codec`。
- 模型权重与运行库体积很大（约 2.9 GB），**不要提交到 Git**；`vendor/` 已在 `.gitignore`。
- 引擎和权重来自你本机的 qwentts.cpp 部署；本仓库不附带二进制。

如果引擎在别处，写 `config.local.json`：

```json
{
  "engine": {
    "url": "http://127.0.0.1:27117",
    "autostart": true,
    "exe": "D:/tts/tts-server.exe",
    "model": "D:/tts/models/qwen-talker-1.7b-customvoice-Q8_0.gguf",
    "codec": "D:/tts/models/qwen-tokenizer-12hz-Q8_0.gguf"
  }
}
```

## 3. 冷启动

`engine.autostart` 为真且引擎未监听时，`say.py` 会用下面的命令拉起它：

```
tts-server.exe --model <model> --codec <codec> --port <port>
```

- 首次加载权重约 10~40 秒（取决于磁盘和显存）。
- 进程以无窗口、分离方式启动，不阻塞 agent。
- 追加参数可写在 `engine.extra_args`。
- **Windows 非 ASCII 路径**：引擎按 ANSI 解析 argv。若技能目录含中文，
  `say.py` 会切到引擎目录并传相对路径，避免路径乱码导致 "Cannot open ..."。

## 4. 连接其他引擎

只要满足第 1 节的协议即可：

```json
{
  "engine": {
    "url": "http://127.0.0.1:8000",
    "autostart": false
  }
}
```

注意：

- 返回必须是 24 kHz s16le 单声道 PCM；其他采样率需要改 `say.py` 的 `SAMPLE_RATE`
  与播放前的重采样逻辑。
- 若服务不提供 `GET /v1/models`，把 `autostart` 设为 `false`，`say.py` 仍会直接尝试合成；
  但 `--status` 的 reachable 会显示为 false。
- 远端服务可用 `AGENT_TTS_URL` 临时覆盖。

## 5. 端口选择

| 端口 | 说明 |
|---|---|
| 27117 | 本技能默认端口（避开其他项目常用的 27017） |
| 27017 / 27015 / 27016 | 历史项目常用端口，别混用，容易互相干扰 |

改端口只需改 `engine.url`（或设 `AGENT_TTS_PORT`）。
