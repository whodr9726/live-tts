# Third-Party Notices

This repository's own code is licensed under the MIT License (see `LICENSE`).
The following third-party components are distributed through GitHub Releases
or used at runtime. They are not covered by this repository's MIT license.

## qwentts.cpp

- Source: https://github.com/ServeurpersoCom/qwentts.cpp
- License: MIT
- Copyright (c) 2023-2026 The omnivoice.cpp authors
- Distributed as: `tts-server.exe` and `ggml*.dll` (when included in a release)
- License text: `licenses/qwentts.cpp-LICENSE`

## ggml

- Source: https://github.com/ggml-org/ggml
- License: MIT
- Copyright (c) 2023-2026 The ggml authors
- Distributed as: `ggml*.dll`
- License text: `licenses/ggml-LICENSE`

## Qwen3-TTS model weights

- Upstream model: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
  https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
- GGUF conversion: Serveurperso/Qwen3-TTS-GGUF
  https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF
- License: Apache-2.0
- Changes: converted from the original checkpoint to GGUF and quantized to
  Q8_0; the RVQ codec/tokenizer paths remain F32 per the converter's defaults.
- Distributed as: `qwen-talker-1.7b-customvoice-Q8_0.gguf`,
  `qwen-tokenizer-12hz-Q8_0.gguf`
- License text: `licenses/Qwen3-TTS-LICENSE`

## NVIDIA CUDA runtime (only if bundled)

- Files: `cudart64_12.dll`, `cublas64_12.dll`, `cublasLt64_12.dll`
- License: NVIDIA CUDA Toolkit EULA
  https://docs.nvidia.com/cuda/eula/index.html
- These files may be redistributed only as part of an application with
  material additional functionality, not as a stand-alone product. Do not
  imply NVIDIA sponsorship or endorsement. If they are not bundled, install
  the CUDA 12 runtime from NVIDIA.
- License text (if bundled): include the CUDA EULA alongside the release
  assets.
