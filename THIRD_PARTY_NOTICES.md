# 第三方组件说明

ForgeCLI 由 [ytinyx](https://github.com/ytinyx) 维护。以下组件用于实现终端界面、模型连接、配置校验和网络通信，保留各自的名称、来源与许可证。

本表列出 `pyproject.toml` 中的直接运行依赖；版本及许可证已与当前锁定版本的安装包元数据核对。

| 组件 | 当前锁定版本 | 用途 | 来源与许可证 |
| --- | --- | --- | --- |
| Textual | 8.2.5 | 终端界面 | [Textualize/textual](https://github.com/Textualize/textual)，MIT |
| Anthropic Python SDK | 0.98.1 | Anthropic 模型接口 | [anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python)，MIT |
| OpenAI Python SDK | 2.34.0 | OpenAI 及兼容模型接口 | [openai/openai-python](https://github.com/openai/openai-python)，Apache-2.0 |
| PyYAML | 6.0.3 | YAML 配置解析 | [yaml/pyyaml](https://github.com/yaml/pyyaml)，MIT |
| Pydantic | 2.13.3 | 数据模型与参数校验 | [pydantic/pydantic](https://github.com/pydantic/pydantic)，MIT |
| MCP Python SDK | 1.30.0 | MCP 工具协议连接 | [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)，MIT |
| HTTPX | 0.28.1 | HTTP 客户端 | [encode/httpx](https://github.com/encode/httpx)，BSD-3-Clause |
| websockets | 16.0 | 本机浏览器界面的 WebSocket 通信 | [python-websockets/websockets](https://github.com/python-websockets/websockets)，BSD-3-Clause |

各组件的完整许可文本随其安装包提供。间接依赖及完整版本解析记录见 `uv.lock`，分别适用其自身许可证；更新依赖时应同步核对本表。

本说明列举直接依赖，不是主项目全部源码的来源或权属清单，也不替代其他适用的版权声明与授权条款。
