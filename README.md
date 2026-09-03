# 多模态浏览器自主操作助手

本项目采用计划文档中确认的混合架构：

- `extension/`：Chrome Manifest V3 插件，负责浏览器感知、动作执行、Side Panel 交互和 Native Messaging 通信。
- `local-agent/`：本地 Generic Agent 服务，复用工作区内的 `GenericAgent/` 源码，负责 Agent Loop、LLM 调用、记忆和技能管理。
- `docs/`：开发计划与设计文档。

## 当前状态

主体代码已经完成，尚未进入测试运行阶段。下一步需要：

1. 配置 GenericAgent 的 `mykey.py`。
2. 加载 `extension/` 为未打包扩展。
3. 注册本地 Native Messaging Host。
4. 运行端到端连通性测试。

## 目录结构

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
│   └── install_host.ps1
└── GenericAgent/
```

## 核心数据流

```text
Side Panel
   │ task.start / user.answer
   ▼
Extension Service Worker
   │ Native Messaging
   ▼
Local Generic Agent Service
   │ browser.request
   ▼
Extension Service Worker
   │ chrome.scripting / chrome.tabs
   ▼
浏览器页面
   │ browser.response
   └──────────────────────────► Local Generic Agent Service
```
