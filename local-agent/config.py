from pathlib import Path

LOCAL_AGENT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = LOCAL_AGENT_ROOT.parent
GENERIC_AGENT_ROOT = WORKSPACE_ROOT / "GenericAgent"
EXTENSION_ROOT = WORKSPACE_ROOT / "extension"
LOG_DIR = LOCAL_AGENT_ROOT / "logs"

NATIVE_HOST_NAME = "com.multimodal.browser_agent"

DEFAULT_BROWSER_TIMEOUT_SECONDS = 20
DEFAULT_TASK_TIMEOUT_SECONDS = 1800

# 是否把智能体关键事件输出到插件。调试瓶颈时可临时设为 False。
PLUGIN_OUTPUT_ENABLED = True

# 日志模式：append=追加到旧日志末尾；clear=每次执行开始时清空日志重新写入。
LOG_MODE = "clear"
