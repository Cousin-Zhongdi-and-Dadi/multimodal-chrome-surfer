# 多模态浏览器自主操作助手

一个基于 Chrome 插件和本地 Generic Agent 服务的多模态浏览器自主操作助手。用户通过自然语言下达任务，系统使用真实浏览器执行网页感知、点击、输入、填写表单、多页面信息整合等操作。

**注意：** 本项目在 Windows 环境下开发，其他平台的兼容性尚未完全测试。

本项目由用户与 Codex 共同开发完成。

## 项目结构

```text
.
├── docs/
│   └── browser-agent-implementation-plan.md
├── extension/
│   ├── manifest.json
│   ├── background.js
│   ├── protocol.js
│   ├── sidepanel.html
│   ├── sidepanel.js
│   ├── content.js
│   ├── offscreen.html
│   └── offscreen.js
├── local-agent/
│   ├── main.py
│   ├── agent_service.py
│   ├── generic_agent_adapter.py
│   ├── native_driver.py
│   ├── browser_bridge.py
│   ├── native_messaging.py
│   ├── messages.py
│   ├── config.py
│   ├── logger.py
│   ├── host_runner.cmd
│   ├── host_manifest.template.json
│   └── install_host.ps1
└── GenericAgent/
```

## 架构说明

- Chrome 插件负责浏览器感知、动作执行、Side Panel 交互和 Native Messaging 通信。
- 本地 Generic Agent 服务负责 Agent Loop、任务规划、LLM 调用、记忆管理和技能沉淀。
- 插件通过 Native Messaging 与本地 Python 服务通信；完整智能体输出写入本地日志，插件只显示工具活动、最终回答和人工追问。

## 环境要求

- Chrome / Chromium 浏览器，支持 Manifest V3
- Python 3.11、3.12 或 3.13
- 可选：`uv` 用于创建虚拟环境

## 安装浏览器插件

1. 打开 Chrome 的扩展管理页面：

```text
chrome://extensions
```

2. 打开右上角的“开发者模式”。
3. 点击“加载已解压的扩展程序”。
4. 选择本项目中的 `extension` 文件夹。
5. 记下扩展 ID，例如：

```text
abcdefghijklmnopqrstuvwxyz
```

## 启用本地智能体服务

### Windows

#### 1. 创建虚拟环境并安装 GenericAgent 依赖

在项目根目录执行：

```powershell
uv venv .venv
uv pip install --python .\.venv\Scripts\python.exe -e ".\GenericAgent[ui]"
```

如果不使用 `uv`，也可以使用：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".\GenericAgent[ui]"
```

#### 2. 配置 GenericAgent 模型密钥

参考 `GenericAgent/mykey_template.py`，在 `GenericAgent/` 下创建或确认 `mykey.py`，并填入可用的模型配置。

#### 3. 注册 Native Messaging Host

将 `<扩展ID>` 替换为实际扩展 ID，然后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\local-agent\install_host.ps1 -ExtensionId <扩展ID>
```

脚本会写入：

```text
HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.multimodal.browser_agent
```

并生成：

```text
local-agent\native-host-manifest.json
```

### macOS

#### 1. 创建虚拟环境并安装 GenericAgent 依赖

在项目根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "./GenericAgent[ui]"
```

如果使用 `uv`：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e "./GenericAgent[ui]"
```

#### 2. 配置 GenericAgent 模型密钥

参考 `GenericAgent/mykey_template.py`，在 `GenericAgent/` 下创建或确认 `mykey.py`。

#### 3. 创建 Native Messaging Host 启动脚本

```bash
cat > local-agent/host_runner.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/.venv/bin/python" "$ROOT/local-agent/main.py"
EOF

chmod +x local-agent/host_runner.sh
```

#### 4. 注册 Native Messaging Host

将 `<扩展ID>` 替换为实际扩展 ID，将 `/绝对路径/` 替换为项目根目录的绝对路径：

```bash
mkdir -p "$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"

cat > "$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.multimodal.browser_agent.json" <<'EOF'
{
  "name": "com.multimodal.browser_agent",
  "description": "Local GenericAgent host for the Multimodal Browser Agent extension.",
  "path": "/绝对路径/local-agent/host_runner.sh",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://<扩展ID>/"
  ]
}
EOF
```

如果使用 Chromium，目录改为：

```text
~/Library/Application Support/Chromium/NativeMessagingHosts
```

### Linux

#### 1. 创建虚拟环境并安装 GenericAgent 依赖

在项目根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "./GenericAgent[ui]"
```

如果使用 `uv`：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e "./GenericAgent[ui]"
```

#### 2. 配置 GenericAgent 模型密钥

参考 `GenericAgent/mykey_template.py`，在 `GenericAgent/` 下创建或确认 `mykey.py`。

#### 3. 创建 Native Messaging Host 启动脚本

```bash
cat > local-agent/host_runner.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/.venv/bin/python" "$ROOT/local-agent/main.py"
EOF

chmod +x local-agent/host_runner.sh
```

#### 4. 注册 Native Messaging Host

将 `<扩展ID>` 替换为实际扩展 ID，将 `/绝对路径/` 替换为项目根目录的绝对路径：

```bash
mkdir -p "$HOME/.config/google-chrome/NativeMessagingHosts"

cat > "$HOME/.config/google-chrome/NativeMessagingHosts/com.multimodal.browser_agent.json" <<'EOF'
{
  "name": "com.multimodal.browser_agent",
  "description": "Local GenericAgent host for the Multimodal Browser Agent extension.",
  "path": "/绝对路径/local-agent/host_runner.sh",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://<扩展ID>/"
  ]
}
EOF
```

Chromium 用户的目录为：

```text
~/.config/chromium/NativeMessagingHosts
```

### 重新加载扩展

任一平台完成 Native Messaging Host 注册后，回到 `chrome://extensions`，点击“Multimodal Browser Agent”的“重新加载”按钮。

## 使用方式

1. 点击 Chrome 工具栏中的扩展图标，打开侧边栏。
2. 当状态显示“已连接”后，在底部输入自然语言任务。
3. 例如：

```text
打开 https://www.baidu.com，并告诉我页面标题
```

4. 任务运行期间，上方会显示“正在工作”和当前正在调用的工具。
5. 最终回复会在侧边栏中以 Markdown 格式显示。

## 配置项

本地配置位于 `local-agent/config.py`。

### 日志模式

```python
LOG_MODE = "append"
```

- `"append"`：追加到旧日志末尾。
- `"clear"`：本地服务启动时清空日志，从头写入。

### 调试开关

```python
DEBUG = False
```

- `True`：输出详细日志，便于开发调试。
- `False`：发布状态，只记录 error 级日志。

### 插件输出开关

```python
PLUGIN_OUTPUT_ENABLED = True
```

关闭后，本地服务不会再向插件发送过程输出；完整日志仍会保留在本地文件中。

## 日志位置

```text
local-agent\logs\local-agent.log
local-agent\logs\agent-output.log
```

发布状态 `DEBUG = False` 时，只记录 error 级别日志。

## 关于 GenericAgent

本项目基于 [GenericAgent](https://github.com/lsdefine/GenericAgent) 构建，并在工作区中保留其源码：

```text
GenericAgent/
```

GenericAgent 采用 MIT License 发布。其设计思想是“最小核心工具 + Agent Loop + 分层记忆 + 自我进化”，本项目的本地智能体服务复用了该框架的 Agent Loop、工具层、记忆层和浏览器驱动能力。

## 免责声明

本项目具备真实浏览器和本地系统操作能力。请勿在未获得授权的网站、账户或环境中使用自动化操作。涉及登录、支付、验证码和不可逆操作时，应通过人工确认后再继续。
