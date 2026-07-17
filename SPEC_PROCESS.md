# SPEC_PROCESS.md — 开发过程记录

> 记录从 brainstorming 到实现过程中与 Superpowers 智能体协作的关键节点、迭代决策、遇到的问题及解决方案。

---

## 一、Brainstorming 关键节点

### 1.1 技术栈选型

**智能体追问**："你倾向于使用什么编程语言来实现 Coding Agent Harness？"

**我的决策**：选择 Python。理由：Python 在 LLM 集成、测试（pytest）、凭据管理（keyring 库）方面生态最成熟，且 Docker 分发友好。系统提示也推荐 Python。

**后续追问链**：
- 主要贡献维度 → 选择 **治理护栏（Governance）**，因它天然由代码构成，最契合"机制必须是代码"的要求
- LLM 供应商 → **OpenAI API（GPT-4o）**，支持自定义 base_url 和 model
- 分发形态 → **Docker 容器**
- 凭据存储 → **OS Keyring**

### 1.2 架构方案取舍

**智能体提出的三种方案**：
1. **单体 Harness 内核（推荐）** — 清晰的 `AgentHarness` 类作为主循环，组件可组合注入
2. Pipeline + 中间件模式 — 责任链模式，每个阶段是独立中间件
3. 插件式微内核 — 插件发现/加载/生命周期管理

**我的决策**：选择方案一。理由：六个维度都需要实现，但治理是深入贡献——单体架构下治理模块可以做得非常深而不引入不必要的抽象层。模块化通过清晰的类/接口边界实现，不需要额外的框架。

### 1.3 三层护栏架构设计

**我提出的设计**：治理护栏分为三层——
1. **规则引擎（RuleEngine）**：基于 `fnmatch` 通配符匹配的黑名单/需审批规则
2. **沙箱边界（Sandbox）**：路径逃逸检测 + 命令白名单
3. **HITL 审批状态机（HITLGate）**：PENDING → APPROVED/REJECTED/TIMEOUT

**智能体追问**是否需要调整，我确认无调整。

### 1.4 凭据管理的补充设计

**用户要求**：LLM 支持自定义基础 URL 和模型，格式按 OpenAI 格式。

**采纳**：`OpenAILLM` 添加 `base_url` 和 `model` 参数，配置文件支持 `llm.base_url` 和 `llm.model` 字段。

---

## 二、至少 3 轮关键迭代

### 迭代 1：Plan 自我审查发现问题

**对话节选**：
> Plan 自审发现：Task 15 的 `test_agent_retries_on_failure` 测试使用了 `pass` 语句，实际未测试重试行为。
> 另一个问题：当 MockLLM 耗尽时，Agent 循环会抛出 `StopIteration` 未被捕获。

**我的处理**：
1. 将 `pass` 改为实际断言 `assert call_count[0] >= 2`
2. 在 `agent.py` 主循环中添加 `except (ParseError, StopIteration)` 捕获
3. 改进停机逻辑：`run_test` 成功时自动停机

### 迭代 2：HITLGate 测试状态污染

**问题**：Task 9 的 HITLGate 测试提交后，CI 显示 3 个测试失败：

```
FAILED test_hitl_gate_pending_then_approve
FAILED test_hitl_gate_pending_then_reject
FAILED test_hitl_gate_list_pending
```

**根因分析**：`HITLGate` 默认 `state_path` 指向 `~/.harness/hitl_state.json`，所有测试共享同一个持久化文件。前序测试写入的 pending 状态未被清理，导致后续测试断言失败。

**我的处理**：
1. 添加 pytest fixture，为每个测试创建独立的临时目录作为 state_path
2. 添加 `shutil.rmtree` 清理
3. 更新 HITL 测试函数签名以使用 fixture

**结果**：19/20 通过（1 skipped 为 Windows 符号链接限制）。

### 迭代 3：Agent 主循环的 JSON 键名不匹配

**问题**：Task 13 实现时发现 PLAN.md 中的测试代码使用 `"action"` 键，但 `Action` 数据类的字段名是 `type`：

```python
# PLAN.md 中的测试代码（有误）
'{"action": "shell", "params": {"command": "ls"}}'

# 实际 Action 数据类定义
@dataclass
class Action:
    type: str  # 不是 "action"
    params: dict
```

**我的处理**：subagent 在实现时自动修正为 `"type"`，并调整 agent 主循环的停机原因字符串为英文以匹配测试断言。

---

## 三、AI 建议与人工修正

### 3.1 采纳的 AI 建议

| 建议 | 来源 | 采纳理由 |
|------|------|---------|
| 使用 `fnmatch` 通配符匹配 | 智能体在 Plan 中提出 | 简单、确定性、无需 LLM 介入 |
| 三层护栏架构（RuleEngine → Sandbox → HITL） | 智能体在 Plan 中设计 | 每层职责清晰，可独立测试 |
| `pyproject.toml` 使用 hatchling 构建 | 智能体自动选择 | 现代 Python 构建工具，零配置 |
| 使用 `tempfile.NamedTemporaryFile` 做配置测试隔离 | 智能体在 Plan 中自动采用 | 避免测试间文件污染 |

### 3.2 推翻或修正的 AI 建议

| 原始建议 | 我的修正 | 原因 |
|---------|---------|------|
| Task 9 使用默认 `state_path` 共享状态 | 改为 per-test 临时路径 | 测试状态污染导致 3 个 FAIL |
| PLAN.md 中 `_classify` 未处理 `TOOL_ERROR` | subagent 发现 `TOOL_ERROR` 未被测试覆盖 | 测试只测试 `UNKNOWN`，所以去掉 `TOOL_ERROR` 分支 |
| 集成测试使用 `"action"` JSON 键 | subagent 自动修正为 `"type"` | 键名必须与 `Action` 数据类字段一致 |

---

## 四、中途遇到的问题汇总

### 4.1 技术问题

| 问题 | 出现于 | 根因 | 解决方案 |
|------|--------|------|---------|
| HITLGate 测试状态污染 | Task 9 | 共享 `~/.harness/hitl_state.json` | 添加 per-test temp fixture |
| Windows 符号链接测试跳过 | Task 8 | `os.symlink` 在 Windows 需管理员/开发者模式 | `@pytest.mark.skipif` 标注 |
| JSON 键名 `"action"` vs `"type"` | Task 13 | PLAN.md 与 Action 数据类定义不一致 | subagent 自动修正 |
| 集成测试 HITL 原因字符串硬编码 | Task 15 | `agent.py` 返回 `"approval timed out"` 而非 `hitl_result.reason` | 修正为使用 `hitl_result.reason` |
| 文件编辑字符串匹配冲突 | Task 9 | `_check_command` 中多处 `return GuardrailResult(...)` 导致 `edit` 操作匹配到错误位置 | 重写整个文件 |
| LF/CRLF 换行符警告 | 多个 Task | Windows 与 Git 换行符策略 | 无害警告，不影响功能 |

### 4.2 流程问题

| 问题 | 说明 | 改进建议 |
|------|------|---------|
| Git 仓库未在 Task 1-2 后初始化 | 用户手动完成前两个 Task 后才发现无 git 环境 | 应在 Task 1 就初始化 git |
| worktree 间依赖管理 | 某些 worktree 合并后，后续 worktree 自动包含最新代码，但若合并前就创建了 worktree 则可能落后 | 应在每个 worktree 创建后 `git pull` 同步 |
| 大型 worktree 数量 | 6 个 worktree 管理成本较高 | 可考虑将紧密耦合的 Task 合并到更少的 worktree |

### 4.3 交付前完整性验证发现的新问题

> 完成全部 16 个 Task 后做端到端验证（2026-07-17），实际跑了 CLI、单元测试、Docker 构建与容器内运行，发现 3 个此前测试与 Plan 都未暴露的真实问题。这印证了"测试通过 ≠ 用户能用"——单元测试在 pytest 内部跑，stdout/stderr 编码被改写、keyring 在 mock 里走假后端，都与真实终端环境行为不同。

| 问题 | 触发条件 | 根因 | 解决方案 |
|------|---------|------|---------|
| **CLI 在 Windows GBK 控制台崩溃** | `harness status` / `approve` / `run` 在 PowerShell/CMD 默认环境直接跑 | `cli.py` 用了 emoji（✅❌ℹ️🚀📋），Windows 控制台默认 cp936 编码无法编码这些字符 → `UnicodeEncodeError: 'gbk' codec can't encode character` | `cli.py` 顶部加 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` |
| **容器内 OS Keyring 完全不可用** | 在 docker 容器里跑 `harness run` 或 `harness setup` | Dockerfile 基于 `python:3.12-slim`，无 D-Bus / gnome-keyring，`keyring` 库落到 `keyring.backends.fail.Keyring`，所有 set/get 抛 `NoKeyringError` | (1) `_get_api_key`：环境变量 `OPENAI_API_KEY` 优先，keyring 兜底；(2) `CredentialManager.get_key/has_key` 捕获 `NoKeyringError` 优雅返回 None/False；(3) `store_key` 抛带提示的 RuntimeError |
| **Docker Desktop 代理 / 镜像源配置** | 本机拉 `python:3.12-slim` 失败 | `daemon.json` 配的镜像加速器 `docker.xuanyuan.me` 需要走 `127.0.0.1:1080` 代理，但本机代理实际端口是 17897 | (1) Settings→Proxies 设 `http://127.0.0.1:17897`；(2) Settings→Docker Engine 清空 `registry-mirrors`，直连 Docker Hub |

### 4.4 修复过程要点

**问题 1（GBK 编码崩溃）**：

- pytest 内部改写了 stdout 编码，3 个 CLI 单元测试全过，但真实 cmd/PowerShell 跑就崩
- 修复仅 4 行（`cli.py:5-9`）：reconfigure 流编码到 utf-8，`errors="replace"` 兜底
- 加 4 个新单元测试覆盖环境变量路径（`test_get_api_key_prefers_env_over_keyring` 等），全套 107 passed

**问题 2（容器内 keyring 不可用）**：

- 实测验证：`docker run --entrypoint python ... -c "import keyring; print(keyring.get_keyring())"` 输出 `fail.Keyring`
- 一开始只改 `_get_api_key` 加环境变量优先，但容器里仍崩——因为 `or cred.get_key(...)` 短路求值时第二段仍执行，fail backend 直接抛栈
- 进一步在 `CredentialManager.get_key/has_key/delete_key` 里捕获 `NoKeyringError`；`store_key` 重抛带提示的 `RuntimeError`（让 `harness setup` 在容器里给出明确报错而不是裸栈）
- 端到端验证：`docker run -e OPENAI_API_KEY=sk-fake coding-agent-harness:test status` 输出 `✅ Harness 已就绪`；不设环境变量时 `harness run` 干净 exit 1

**问题 3（Docker 代理）**：

- 这是环境配置问题，不动代码；记录在 README 的 Docker 章节供交付方参考


---

## 五、对 Brainstorming 技能的反思

### 做得好的方面

1. **追问充分**：智能体对技术选型、架构方案、重点维度做了系统性的追问，没有遗漏关键决策
2. **渐进式确认**：每次呈现一个设计节段，确认后再继续，避免了"一次性设计"导致的返工
3. **方案对比**：提出三种架构方案并分析 trade-offs，帮助我做 informed decision

### 令人不满的方面

1. **Plan 中的测试代码与数据类定义不一致**：`"action"` vs `"type"` 的键名差异在 Plan 阶段未被发现，直到实现阶段才由 subagent 修正。说明 Plan 的 self-review 应更仔细地检查接口一致性。
2. **HITLGate 状态共享问题**：Plan 没有考虑到测试隔离问题，直接使用了默认路径。这属于测试基础设施设计不足。
3. **Windows 兼容性考虑不足**：符号链接测试在 Windows 下被跳过，虽然影响不大，但 Plan 未标注平台差异。

---

## 六、任务完成状态

| Task | 模块 | 状态 | 测试数 | 备注 |
|------|------|------|--------|------|
| 1-2 | 脚手架 + 数据模型 | ✅ 完成 | 7 | 用户手动完成，后补 git init |
| 3 | 配置模块 | ✅ 完成 | 4 | 审查通过 |
| 4 | 凭据管理 | ✅ 完成 | 7 | 审查通过（修复 unused import） |
| 5 | LLM 抽象层 | ✅ 完成 | 6 | 审查通过 |
| 6 | 工具执行器 | ✅ 完成 | 8 | 审查通过 |
| 7 | 治理-规则引擎 | ✅ 完成 | 8 | 审查通过 |
| 8 | 治理-沙箱 | ✅ 完成 | 6 | 审查通过 |
| 9 | 治理-HITLGate | ✅ 完成 | 6 | 修复测试状态污染 |
| 10 | 治理-编排器 | ✅ 完成 | 5 | 审查通过 |
| 11 | 反馈闭环 | ✅ 完成 | 11 | 审查通过 |
| 12 | 记忆模块 | ✅ 完成 | 5 | 审查通过 |
| 13 | Agent 主循环 | ✅ 完成 | 5 | 修正 JSON 键名 |
| 14 | CLI 入口 | ✅ 完成 | 3 | 审查通过 |
| 15 | 集成测试 | ✅ 完成 | 11 | 3 个机制演示通过 |
| 16 | Docker + CI | ✅ 完成 | - | - |

**总计**：91 passed, 1 skipped (Windows symlink), 0 failed

---

## 七、Git 工作流记录

| Worktree | 分支 | Task | 合并到 main |
|----------|------|------|------------|
| `config-credential` | `feat/config-credential` | 3, 4 | ✅ 557f999 |
| `llm-tools` | `feat/llm-tools` | 5, 6 | ✅ 40b3643 |
| `guardrail` | `feat/guardrail` | 7-10 | ✅ 605e6e0 |
| `feedback-memory` | `feat/feedback-memory` | 11, 12 | ✅ 2673bf9 |
| `agent-cli` | `feat/agent-cli` | 13, 14 | ✅ 51f94b9 |
| `integration-docker` | `feat/integration-docker` | 15 | ✅ 16ac18d |