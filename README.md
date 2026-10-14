# OU v0.4 台架工具链

OU 协议 v0.4（SM4-CBC + HMAC-SM3 密封外壳）的 PC 侧台架工具：

- 串口 / TCP 客户端
- 浏览器仪表盘（HTTP + 内嵌单页）
- 一键台架启动器（WSL + Windows USB-TTL）
- 厂商 SDK（`ou_sdk 0.4.1`）密封链路的封装与逐字节对拍

## 组成

| 路径 | 说明 |
|---|---|
| `Tools/ou_crypto.py` | 零依赖 SM4 / SM3 + 密封外壳 + 防重放窗口。参考实现，同时是 SDK 正确性的独立度量基线 |
| `Tools/ou_serial_test.py` | 串口 / TCP 客户端：遥测 JSON 行输出，`SET_STREAM` / `ARM` / `SET_MODE` / `SET_PWM` / `PARAM_SET` 下发并打印 ack |
| `Tools/ou_dashboard.py` | 浏览器仪表盘。解密封包卡片 + 帧率 + 各类型计数 + 最近帧 sealed/plaintext hex + 事件日志；默认只读，`--allow-control` 解锁控制类下发 |
| `Tools/ou_bench.py` | 一键台架启动器：自动挑 COM 口 → 逐波特率探测（判据=能否验签）→ 起串口↔TCP 桥 → 开浏览器 → 收摊 |
| `Tools/ou_sdk_bridge.py` | 厂商 SDK 的 ctypes 绑定，接口与 `ou_crypto.SerialShell` 一致 |
| `Tools/ou_sdk_interop.py` | SDK ↔ Python 参考实现逐字节对拍验收 |
| `Tools/ou_sdk_wrapper/` | C++ `SealedLink`（密封链路）+ 扁平 C ABI + `ou_link_probe` 自检程序（内置 16 条 golden 向量） |

## 依赖

- **Python 3.8+**。协议与密码学**全部内置，无第三方依赖**（不需要 `cryptography`，也不需要 `gmssl`）。
- 只有走**真实串口**时才需要 `pyserial`；走 TCP（SITL / 台架桥）零依赖。
- `--decoder sdk` 需要**厂商 SDK `ou_sdk 0.4.1`**（`include/` + `lib/`），用环境变量 `OU_SDK_ROOT` 指向它。该 SDK 为闭源产物，**未包含在本仓库**。
- 构建封装库需要 cmake（或直接用 `Tools/ou_sdk_wrapper/Makefile`）。
- `--self-test` 会拿 `libraries/OU_Protocol/` 下的生成头文件与 golden 向量做对拍（这两个文件已随本仓库提供）；只跑实时链路不需要它们。

## 快速开始

```bash
# 自检（不需要硬件、不需要 SDK）
python3 Tools/ou_crypto.py
python3 Tools/ou_serial_test.py --self-test
python3 Tools/ou_dashboard.py --self-test
python3 Tools/ou_bench.py --self-test

# SDK 后端：构建封装库并对拍
export OU_SDK_ROOT=/path/to/ou-sdk-0.4.1
cmake -S Tools/ou_sdk_wrapper -B Tools/ou_sdk_wrapper/build -DOU_SDK_ROOT="$OU_SDK_ROOT"
cmake --build Tools/ou_sdk_wrapper/build
python3 Tools/ou_sdk_bridge.py --self-test
python3 Tools/ou_sdk_interop.py
```

```bash
# 接飞控
python3 Tools/ou_dashboard.py --port /dev/ttyUSB0 --baud 57600   # 浏览器看解密数据
python3 Tools/ou_serial_test.py --port /dev/ttyUSB0 --baud 57600 --listen
python3 Tools/ou_bench.py                                        # 一键台架
```

## 说明

- `--decoder` 默认 `sdk`；`--decoder python` 走内置的零依赖实现，是 SDK 缺失时的退路（也是 Windows 原生 Python 唯一可用的后端，因为封装库是 Linux/WSL 的 `.so`）。
- **下行**（飞控 → PC）的验签、防重放、SM4-CBC 解密、去 PKCS#7 由厂商 `ShellCrypto::open()` 完成；**上行**输出与厂商 `ShellCrypto::seal()` 逐字节相同。
- 联调使用的是**开发占位密钥**，**不可用于量产**。
