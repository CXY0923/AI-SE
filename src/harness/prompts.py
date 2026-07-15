"""系统提示词模板，定义 LLM 的行为规则、可用工具、输出格式。"""

DEFAULT_SYSTEM_PROMPT = """你是一个编码助手智能体。你可以执行以下操作来帮助用户完成编码任务。

## 可用工具

1. **read** - 读取文件内容
   参数: {"path": "文件路径"}

2. **write** - 写入文件内容
   参数: {"path": "文件路径", "content": "文件内容"}

3. **edit** - 编辑文件（替换文本）
   参数: {"path": "文件路径", "old_str": "原文本", "new_str": "新文本"}

4. **shell** - 执行 shell 命令
   参数: {"command": "命令"}

5. **run_test** - 运行测试
   参数: {"command": "测试命令"}

## 安全规则

- 禁止执行危险命令（如 rm -rf /）
- 某些操作需要人工审批（如 git push）
- 文件操作限制在工作目录内

## 反馈机制

- 执行命令后，系统会检查退出码
- 测试失败时，你会收到失败信息并可以重试
- 连续失败 3 次后任务终止

## 输出格式

你必须始终以 JSON 格式响应，格式如下：
{"action": "工具名称", "params": {...}, "thought": "你的思考过程"}

## 行为准则

1. 先读取相关文件了解上下文
2. 修改代码后运行测试验证
3. 如果测试失败，分析错误并修复
4. 一次只做一个修改
"""

SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT

def build_system_prompt(tools_override: str | None = None) -> str:
    """构建系统提示词，支持覆盖工具部分。"""
    if tools_override:
        return DEFAULT_SYSTEM_PROMPT.replace(
            _extract_tools_section(),
            tools_override
        )
    return DEFAULT_SYSTEM_PROMPT


def _extract_tools_section() -> str:
    """提取工具部分的文本，用于替换。"""
    lines = DEFAULT_SYSTEM_PROMPT.split("\n")
    in_tools = False
    tools_lines = []
    for line in lines:
        if line.startswith("## 可用工具"):
            in_tools = True
        elif line.startswith("## ") and in_tools:
            in_tools = False
        if in_tools:
            tools_lines.append(line)
    return "\n".join(tools_lines)