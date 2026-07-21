# Brooks ICT Hybrid 完整分享包

> **Snapshot notice / 快照声明**：本仓为某时点快照，**非 source of truth**。本地 skill/scanner 持续演进，此包可能落后数版；版本以 `brooks-ict-hybrid/SKILL.md` 内 Version 字段为准（当前同步：slim-2026-07-21b，2026-07-21）。内部硬编码的 `/home/ubuntu/...` 路径请改为你自己的环境。


版本：2026-07-12j

公开分享版：skill + 本地扫描器。仓库不包含个人交易日志、历史行情、账号密钥或本机运行配置。

本包包含：

- `brooks-ict-hybrid/`：交易分析 skill。
- `trading_scanner_service/`：本地行情与扫描器服务。
- `start_scanner.sh`：Linux/macOS 启动脚本。
- `start_scanner.bat`：Windows 启动脚本。

## 快速开始

```bash
git clone https://github.com/jia97776-tech/brooks-ict-hybrid-kit.git
cd brooks-ict-hybrid-kit
./start_scanner.sh
```

Windows 下载 ZIP 解压后，双击 `start_scanner.bat`。

## 1. 安装 skill

### Codex

把整个 `brooks-ict-hybrid` 文件夹放到：

```text
~/.codex/skills/brooks-ict-hybrid
```

### Claude

把整个 `brooks-ict-hybrid` 文件夹放到：

```text
~/.claude/skills/brooks-ict-hybrid
```

安装后重新开启一个会话。

## 2. 启动扫描器

要求：Python 3.10 或更高版本。基础扫描仅使用 Python 标准库，不需要 API Key。

Linux/macOS：

```bash
chmod +x start_scanner.sh
./start_scanner.sh
```

Windows：

```bat
start_scanner.bat
```

也可以手动启动：

```bash
cd trading_scanner_service
python3 run_server.py
```

Windows 若没有 `python3` 命令：

```bat
cd trading_scanner_service
py -3 run_server.py
```

默认地址：

```text
http://127.0.0.1:8001
```

## 3. 验证

浏览器或命令行访问：

```text
http://127.0.0.1:8001/healthz
```

返回 `{"ok":true}` 即正常。

常用接口：

```text
GET  /price/BTC
GET  /bars?symbol=EURUSD&tf=M15
POST /scanner/run-once?mode=both
GET  /scanner/status
```

## 4. 使用提示

- 先启动扫描器，再让 AI 使用 `brooks-ict-hybrid` 做实时分析。
- Scanner 只当地图，最终动作仍由 skill 的 PA + ICT 规则过滤。
- 止损先声明 M1/M5、M15 或 H4 整层级别，列全候选锚后锁定；成交后只可维持或收紧，禁止扩损。
- 基础行情接口无需账户密钥，但需要能访问对应公开行情源。
- 飞书主动推送与 Claude 二审是本机定制可选功能，不包含任何原用户账号、密钥或配置。
- 本包不含个人交易日志、papertrack 记录、运行缓存或历史行情数据库。

## 风险说明

该工具用于研究和辅助判断，不保证盈利，不构成投资建议。先做模拟盘或小仓验证。
