# Coding Agent Harness — 设计规约（SPEC）

> **版本**: 1.0  
> **状态**: 已批准  
> **核心等式**: Agent = LLM + Harness

---

## 1. 问题陈述

### 1.1 要解决的问题

当前 LLM 在编码场景中的使用方式大多停留在"对话式补全"——用户逐条输入指令，LLM 逐条回复。这种方式缺乏工程化能力：没有自动化的上下文管理、没有安全护栏、没有对执行结果的客观验证与自我修正机制。

**Coding Agent Harness** 的目标是：将一个只会"决定下一步做什么"的 LLM，封装成一个能稳定、可靠地完成编码任务的自动化系统。它负责组织上下文、调用 LLM、解析动作、执行工具、检查结果、自我修正——所有"LLM 之外"的工程能力都由 harness 的代码实现。

### 1.2 目标用户

- 需要自动化编码辅助的软件开发者
- 希望让 LLM 在安全边界内自主完成代码修改、测试运行、项目维护的团队
- 对 AI 工程化感兴趣、希望理解"Agent = LLM + Harness"这个等式的学习者

### 1.3 为什么值得做

当 LLM 能完成大部分"思考"时，工程师的真正价值落在治理、反馈、安全、工程化这一层。本项目通过亲手实现一个 harness 内核，回答"一个可靠的 AI 编码系统到底需要哪些工程"。

---

## 2. 用户故事

以下用户故事遵循 INVEST 原则（Independent, Negotiable, Valuable, Estimable, Small, Testable）：

1. **US-01：安全执行编码任务**  
   作为开发者，我希望让 agent 在我的项目目录内自动修改代码并运行测试，这样我可以节省重复劳动。同时我希望 agent 不会执行危险的命令（如 `rm -rf /`），以确保我的系统安全。

2. **US-02：危险操作拦截与审批**  
   作为开发者，我希望当 agent 试图执行需要人工确认的操作（如 `git push`、删除文件）时，系统能暂停并提示我审批，这样我可以在关键操作上有最终决定权。

3. **US-03：自动修复失败的测试**  
   作为开发者，我希望 agent 在修改代码后运行测试，如果测试失败，它能自动分析失败原因并尝试修复，这样我可以减少手动调试的循环。

4. **US-04：跨会话记忆**  
   作为开发者，我希望 agent 能记住我之前的项目约定和历史决策（如"不要修改 `config.py`"），这样每次启动新会话时不需要重复说明。

5. **US-05：凭据安全配置**  
   作为开发者，我希望在首次使用 harness 时能通过安全的方式录入我的 API Key，并且系统不会在任何地方明文存储或显示它，这样我的凭据不会泄露。

6. **US-06：自定义 LLM 端点**  
   作为开发者，我希望能够使用任何兼容 OpenAI 格式的 API 端点（如本地 vLLM、ollama 或其他供应商），而不必修改代码。

7. **US-07：Docker 化分发**  
   作为运维人员，我希望能够通过一条 Docker 命令在任何机器上运行 harness，并且通过环境变量或挂载卷安全配置 API Key。

---

## 3. 功能规约

### 3.1 决策封装（Agent Loop）

**模块**: `harness/agent.py`

| 功能 | 输入 | 行为 | 输出 |
|------|------|------|------|
| 主循环 | 用户任务描述 (string) | 按轮次组织上下文 → 调用 LLM → 解析动作 → 治理检查 → 执行 → 反馈 → 停机判断 | 最终结果报告 |
| 上下文构建 | 任务、历史记录、记忆、反馈 | 将当前状态组装为 LLM 可理解的上下文文本 | context string |
| 动作解析 | LLM 响应文本 | 解析 JSON 格式的动作描述 | `Action` 对象 / `ParseError` |
| 停机判断 | 反馈结果、轮次计数 | 检查是否达到终止条件 | True/False |

**边界条件**：
- 最大轮次：默认 20，可配置
- 连续失败 3 次 → 停机
- HITL 拒绝 → 停机
- 解析失败 3 次 → 停机

### 3.2 动作/工具（ToolExecutor）

**模块**: `harness/tools.py`

| 工具 | 动作类型 | 参数 | 返回值 | 错误处理 |
|------|---------|------|--------|---------|
| 读文件 | `read` | `path` | `ActionResult(stdout=文件内容)` | 文件不存在 → exit_code=1 |
| 写文件 | `write` | `path, content` | `ActionResult(success=True)` | 路径越界 → 拒绝 |
| 编辑文件 | `edit` | `path, old_str, new_str` | `ActionResult(success=True)` | 模式不匹配 → exit_code=1 |
| 执行 Shell | `shell` | `command` | `ActionResult(exit_code, stdout, stderr)` | 命令不在白名单 → 拒绝 |
| 运行测试 | `run_test` | `command` | `ActionResult(exit_code, stdout, stderr)` | 同 shell |

### 3.3 上下文与记忆（Memory）

**模块**: `harness/memory.py`

| 功能 | 说明 |
|------|------|
| 会话内记忆 | 维护 `List[ConversationTurn]`，按 token 估算截断（保留最近 N 轮） |
| 跨会话记忆 | 以 JSON 文件存储于 `~/.harness/memory.json`，含项目级决策记录 |
| 信息检索 | 关键词匹配 + 最近 N 条优先（轻量，不接入向量库） |

### 3.4 治理护栏（Guardrail）—— 主要贡献

**模块**: `harness/guardrail.py`

#### 3.4.1 规则引擎（RuleEngine）

| 功能 | 输入 | 输出 |
|------|------|------|
| 黑名单匹配 | `Action` | `GuardrailResult(DENY/ALLOW, reason)` |
| 需审批匹配 | `Action` | `GuardrailResult(PENDING, reason)` |

**规则来源**：YAML 配置文件 `~/.harness/rules.yaml`
**匹配算法**：精确匹配 + `fnmatch` 通配符匹配

#### 3.4.2 沙箱边界（Sandbox）

| 功能 | 说明 |
|------|------|
| 工作目录锁定 | 所有文件操作限定在项目目录内 |
| 命令白名单 | 允许的命令集合（可配置） |
| 路径逃逸检测 | `os.path.realpath()` 解析后检查是否越界 |

#### 3.4.3 HITL 审批状态机（HITLGate）

**状态**：`PENDING → AWAITING_APPROVAL → APPROVED | REJECTED | TIMEOUT`

| 功能 | 说明 |
|------|------|
| 交互式审批 | CLI 提示用户审批/拒绝/查看详情 |
| 超时机制 | 默认 5 分钟，可配置 |
| 状态持久化 | `~/.harness/hitl_state.json` |

### 3.5 反馈闭环（FeedbackLoop）

**模块**: `harness/feedback.py`

| 组件 | 职责 |
|------|------|
| 校验器链 | `ExitCodeValidator`（检查 exit_code == 0）、`ContentValidator`（检查产物） |
| 失败分类器 | `COMPILE_ERROR` / `TEST_FAILURE` / `TIMEOUT` / `TOOL_ERROR` / `UNKNOWN` |
| 重试策略 | 最多 3 次重试，重试时注入失败原因到上下文 |

### 3.6 配置（Config）

**模块**: `harness/config.py`

**配置文件**：`~/.harness/config.yaml` 或项目目录下的 `.harness.yaml`

```yaml
harness:
  max_rounds: 20
  llm:
    provider: openai
    base_url: https://api.openai.com/v1
    model: gpt-4o
    temperature: 0.2
  guardrails:
    deny_commands:
      - pattern: "rm -rf /"
        reason: "禁止删除根目录"
    require_approval:
      - pattern: "git push"
        reason: "推送代码需要人工确认"
    hitl_timeout: 300
  sandbox:
    work_dir: "."
    allow_commands: [git, npm, python, pytest, cat, ls, mkdir, cp]
  feedback:
    max_retries: 3
```

### 3.7 凭据管理（CredentialManager）

**模块**: `harness/credential.py`

| 功能 | 说明 |
|------|------|
| 存储 key | `store_key(service, key)` → 存入 OS Keyring |
| 读取 key | `get_key(service)` → 返回 key（仅内存中明文） |
| 删除 key | `delete_key(service)` |
| 安全录入 | 首次运行引导用户隐藏输入 |

### 3.8 CLI 入口

**模块**: `harness/cli.py`

| 命令 | 功能 |
|------|------|
| `harness setup` | 安全录入 API Key |
| `harness status` | 查看配置状态（不显示明文 key） |
| `harness run "<task>"` | 运行一个编码任务 |
| `harness config` | 查看/编辑配置 |
| `harness approve` | 查看待审批的 HITL 请求 |

---

## 4. 非功能性需求

### 4.1 性能
- 单轮循环延迟：主要由 LLM API 调用时间决定，harness 本身开销 < 100ms
- 记忆检索：`O(N)` 线性扫描，N < 1000 条

### 4.2 安全（含凭据威胁模型）

**凭据威胁模型**：

| 威胁 | 风险等级 | 对策 |
|------|---------|------|
| API Key 硬编码在源码中 | 高 | 源码中无任何凭据占位符，全部通过 OS Keyring 管理 |
| API Key 出现在 Git 历史中 | 高 | `.gitignore` 排除 `.env`、`*.key`、`credentials*`；提交前自查 |
| API Key 出现在日志/终端 history | 中 | 日志中屏蔽 key 输出；隐藏输入避免 shell history |
| 进程内存被读取 | 低 | key 仅在内存中短期存在，用完后及时清理变量 |
| OS Keyring 被破解 | 低 | 依赖 OS 级别的安全机制（Windows Credential Manager / macOS Keychain） |

**安全措施**：
- 所有 API key 通过操作系统钥匙串存储
- 首次运行引导用户安全录入 key（隐藏输入）
- 查看状态时不得回显明文
- 日志中自动屏蔽 key 内容

### 4.3 可用性
- 单条命令即可运行：`docker run harness "task"`
- 首次运行引导式配置
- 清晰的错误提示（不堆栈 trace）

### 4.4 可观测性
- 日志记录每轮循环的关键事件
- 记录治理拦截（含时间、动作、裁决结果）
- 记录反馈闭环（含失败类型、重试次数）

---

## 5. 系统架构

### 5.1 组件图

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLI (harness/cli.py)                       │
│             setup | status | run | config | approve               │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│                    AgentHarness (harness/agent.py)                 │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  AgentLoop:                                                │   │
│  │  1. build_context() ─→ 组织上下文 (memory + history + feedback)│   │
│  │  2. call_llm()      ─→ LLM 抽象层                           │   │
│  │  3. parse_action()  ─→ JSON → Action                        │   │
│  │  4. apply_guardrails() ─→ RuleEngine → Sandbox → HITLGate  │   │
│  │  5. execute_action() ─→ ToolExecutor                        │   │
│  │  6. run_feedback()  ─→ ValidatorChain → FailureClassifier  │   │
│  │  7. check_stop()    ─→ 停机判断                             │   │
│  └───────────────────────────────────────────────────────────┘   │
└──┬──────────┬──────────┬──────────┬──────────┬────────────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐
│ LLM  │ │ToolExec  │ │Guardrail │ │Feedback│ │ Memory   │
│层    │ │(tools.py)│ │(guardrail│ │(feedback│ │(memory.py)│
│(llm.)│ │          │ │ .py)     │ │ .py)   │ │          │
│py)   │ │          │ │ 主贡献   │ │        │ │          │
└──────┘ └──────────┘ └──────────┘ └────────┘ └──────────┘
```

### 5.2 数据流

```
用户输入任务
    │
    ▼
build_context() ─── 加载记忆 + 历史 + 反馈
    │
    ▼
LLM.generate()  ─── 通过 LLM 抽象层
    │
    ▼
parse_action()  ─── 解析为结构化 Action
    │
    ▼
apply_guardrails()
    ├── ALLOW    ─→ 执行
    ├── DENY     ─→ 记录日志，跳过
    ├── PENDING  ─→ HITL 审批 → (APPROVED|REJECTED|TIMEOUT)
    │
    ▼
execute_action() ── ToolExecutor 执行
    │
    ▼
run_feedback()  ─── 校验器 → 分类 → 回灌
    │
    ▼
check_stop()    ─── 是否停机？
    ├── 否 → 回到 build_context()
    └── 是 → 输出最终结果
```

### 5.3 外部依赖

| 依赖 | 用途 | 可选性 |
|------|------|--------|
| OpenAI Python SDK | 调用 OpenAI 兼容 API | 可选（可用 MockLLM 替代） |
| keyring 库 | 操作系统钥匙串接口 | 可选（可回退到加密文件） |
| PyYAML | 解析 YAML 配置 | 是 |
| pytest | 测试框架 | 仅开发/测试 |

---

## 6. 数据模型

### 6.1 核心实体

```python
@dataclass
class Action:
    type: str                    # read | write | edit | shell | run_test
    params: dict                 # 参数
    thought: str = ""            # LLM 的思考过程

@dataclass
class ActionResult:
    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    output_path: str = ""

@dataclass
class GuardrailResult:
    verdict: Verdict             # ALLOW | DENY | PENDING | APPROVED | REJECTED | TIMEOUT
    reason: str = ""
    layer: str = ""              # rule_engine | sandbox | hitl

@dataclass
class FeedbackResult:
    passed: bool
    category: FailureCategory    # COMPILE_ERROR | TEST_FAILURE | TIMEOUT | TOOL_ERROR | UNKNOWN
    details: str = ""
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class ConversationTurn:
    action: Action
    result: ActionResult
    feedback: FeedbackResult | None = None
```

### 6.2 枚举类型

```python
class Verdict(Enum):
    ALLOW = "allow"
    DENY = "deny"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"

class FailureCategory(Enum):
    COMPILE_ERROR = "compile_error"
    TEST_FAILURE = "test_failure"
    TIMEOUT = "timeout"
    TOOL_ERROR = "tool_error"
    UNKNOWN = "unknown"
```

### 6.3 文件存储

| 文件 | 格式 | 用途 |
|------|------|------|
| `~/.harness/config.yaml` | YAML | 用户配置 |
| `~/.harness/rules.yaml` | YAML | 护栏规则 |
| `~/.harness/memory.json` | JSON | 跨会话记忆 |
| `~/.harness/hitl_state.json` | JSON | HITL 状态持久化 |

---

## 7. 凭据与分发设计

### 7.1 凭据存储方案

**方案**：OS Keyring（Python `keyring` 库）

| 平台 | 后端 |
|------|------|
| Windows | Windows Credential Manager |
| macOS | macOS Keychain |
| Linux | Secret Service (dbus) / GNOME Keyring |

**流程**：
1. 首次运行 `harness setup` → 提示输入 API Key → 隐藏输入 → 存入 OS Keyring
2. 运行时 `CredentialManager.get_key("openai")` → 从 OS Keyring 读取
3. 更新/清除通过 `harness setup` 或 `harness config` 管理
4. 回退方案：如果 OS Keyring 不可用，使用 AES 加密文件 + 主密码

### 7.2 分发形态

**方案**：Docker 容器

**Dockerfile** 关键点：
- 基于 `python:3.12-slim`
- 安装依赖
- 复制源码
- 声明 `VOLUME /root/.harness` 用于持久化配置和记忆
- 入口点：`harness` CLI

**Docker 运行方式**：
```bash
# 构建
docker build -t coding-agent-harness .

# 运行（首次需要配置 key）
docker run -it -v harness-data:/root/.harness coding-agent-harness setup

# 运行任务
docker run -it -v harness-data:/root/.harness \
  -v $(pwd):/workspace -w /workspace \
  coding-agent-harness run "修复所有测试失败"
```

---

## 8. 技术选型与理由

| 决策 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.12+ | 生态丰富（LLM SDK、keyring、pytest）、快速迭代、CLI 工具成熟 |
| LLM 接口 | OpenAI 兼容格式 | 最广泛的兼容性，可接入任何 OpenAI 兼容 API |
| 凭据管理 | OS Keyring (`keyring`) | 跨平台安全存储，无需管理额外密码 |
| 测试框架 | pytest | Python 标准测试框架，fixture 机制适合 mock 注入 |
| 正确性验证 | pytest | 覆盖所有核心模块 |
| 配置格式 | YAML | 人类可读，支持注释 |
| 分发 | Docker | 跨平台、零依赖安装、环境隔离 |
| 包管理 | uv/pip | 快速依赖解析 |

---

## 9. 验收标准

| 模块 | 通过标准 |
|------|---------|
| Agent Loop | MockLLM 下 3 轮循环可正常完成，停机判断正确 |
| ToolExecutor | 5 种工具均可正常执行，沙箱拒绝越界操作 |
| Guardrail | 黑名单规则正确拦截、沙箱拒绝路径逃逸、HITL 状态机三种结局均正确 |
| FeedbackLoop | 正确分类失败类型，重试机制在 3 次内停止 |
| Memory | 会话内记忆正确截断、跨会话记忆可持久化 |
| Config | 配置加载正确，缺失字段使用默认值 |
| 凭据管理 | 存储/读取/删除/状态检查均正常，查看状态不显示明文 |
| 测试覆盖 | 核心模块单元测试覆盖率 ≥ 80%，所有测试可一键运行 |

---

## 10. 风险与未决问题

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| OS Keyring 在某些 Linux 环境不可用 | 凭据无法安全存储 | 回退到加密文件方案 |
| Docker 容器内无法访问宿主机 OS Keyring | 容器内需要安全配置 key | 通过挂载卷 + 首次运行引导 |
| LLM 输出格式不稳定 | 动作解析失败 | 多次重试解析 + 降级策略 |
| 文件编辑中 `old_str` 匹配失败 | 编辑工具失效 | 提供回退到 rewrite 整个文件 |
| 沙箱路径逃逸检测不完善 | 安全风险 | 多层路径解析 + 单元测试覆盖边界情况 |

**未决问题**：
- 是否需要在 Docker 环境中支持从环境变量读取 key（作为 OS Keyring 的补充）？
- HITL 超时后是否应自动重试或发送通知？

---

## 11. 领域与机制设计（A 类专属）

### 11.1 领域分析

**领域**：编码自动化（Coding Agent）

| 机制维度 | 领域映射 | 编码实现方式 |
|----------|---------|-------------|
| **反馈信号** | 测试运行结果、编译错误、进程退出码 | `ExitCodeValidator` + `ContentValidator` — 确定性代码，解析 ActionResult 判定 |
| **危险动作** | 危险 shell 命令、路径逃逸、未授权发布 | `RuleEngine`（通配符匹配）+ `Sandbox`（路径解析）— 确定性代码 |
| **所需工具** | 读写文件、编辑文件、执行 shell、运行测试 | `ToolExecutor` 注册制 — 代码实现 |
| **记忆需求** | 项目约定、历史决策、已修改文件 | `Memory` JSON 存储 + 最近 N 条优先 — 代码实现 |

### 11.2 重点维度：治理护栏

选择治理护栏作为主要贡献的理由：

1. **机制密集**：三层架构（规则引擎 → 沙箱 → HITL）天然由确定性代码构成，每一层都可以独立测试
2. **最契合"机制必须是代码"**：规则匹配是 `fnmatch` 算法、沙箱是路径解析、HITL 是状态机——没有一行提示词
3. **工程价值最高**：安全护栏是 harness 投入生产环境最关键的保障

### 11.3 移除 LLM 后的可测试性

| 模块 | 测试方式 | 确定性? |
|------|---------|---------|
| RuleEngine | 构造 `Action(command="rm -rf /")` → 断言 DENY | ✅ |
| Sandbox | 构造路径逃逸 Action → 断言 DENY | ✅ |
| HITLGate | 模拟超时/批准/拒绝 → 断言状态转换 | ✅ |
| FeedbackLoop | 构造 `ActionResult(exit_code=1)` → 断言分类 | ✅ |
| ToolExecutor | 构造 Action → 断言执行结果 | ✅ |
| AgentLoop | MockLLM 预设响应 → 断言循环流程 | ✅ |
| Memory | 读写 JSON 文件 → 断言内容正确 | ✅ |

---

## 附录 A：目录结构

```
项目根/
  ├── src/
  │   └── harness/
  │       ├── __init__.py
  │       ├── agent.py          # Agent 主循环
  │       ├── llm.py            # LLM 抽象层 (OpenAILLM + MockLLM)
  │       ├── action.py         # 数据模型 (Action, ActionResult, 等)
  │       ├── tools.py          # 工具执行器
  │       ├── guardrail.py      # 治理护栏（主要贡献）
  │       ├── feedback.py       # 反馈闭环
  │       ├── memory.py         # 上下文与记忆
  │       ├── config.py         # 配置加载
  │       ├── credential.py     # 凭据管理
  │       └── cli.py            # CLI 入口
  ├── tests/
  │   ├── unit/
  │   │   ├── test_agent.py
  │   │   ├── test_llm.py
  │   │   ├── test_action.py
  │   │   ├── test_tools.py
  │   │   ├── test_guardrail.py
  │   │   ├── test_feedback.py
  │   │   ├── test_memory.py
  │   │   ├── test_config.py
  │   │   └── test_credential.py
  │   └── integration/
  │       └── test_harness_integration.py
  ├── pyproject.toml
  ├── Dockerfile
  ├── .gitignore
  ├── .gitlab-ci.yml
  ├── README.md
  ├── SPEC.md
  ├── PLAN.md
  ├── SPEC_PROCESS.md
  ├── AGENT_LOG.md
  └── REFLECTION.md
```

---

*本规约经 brainstorming 技能引导，与用户通过多轮对话共同设计完成。*