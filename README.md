# Coding Agent Harness

> **Agent = LLM + Harness** — 一个自己编码实现的 agent 内核，将 LLM 的"决策"封装为稳定、可靠的工程系统。

---

## 项目简介

Coding Agent Harness 是一个面向软件开发场景的自动化编码智能体内核。核心等式是 **Agent = LLM + Harness**：LLM 只负责"决定下一步做什么"，其余都是工程。

本项目实现了 **六个维度** 的 harness 机制，以 **治理护栏** 为主要贡献：

| 维度 | 说明 | 实现 |
|------|------|------|
| **决策封装** | 组织上下文 → 调用 LLM → 解析动作 → 分发执行 → 回灌结果 → 停机判断 | `AgentHarness` 主循环 |
| **动作/工具** | 读写文件、执行 shell、运行测试 | `ToolExecutor` |
| **上下文与记忆** | 会话内历史 + 跨会话知识持久化 | `Memory` |
| **治理护栏** | 规则引擎 + 沙箱边界 + HITL 审批状态机（**主要贡献**） | `Guardrail` 三层架构 |
| **反馈闭环** | 退出码校验 + 失败分类 + 重试策略 | `FeedbackLoop` |
| **配置** | YAML 声明式配置 | `HarnessConfig` |

### 机制演示（Mock LLM 确定性测试）

```
1. 护栏拦截 → 传入 Action("rm -rf /")，断言 Verdict.DENY
2. 反馈闭环 → 注入失败 ActionResult，agent 自动重试修正
3. HITL 审批 → PENDING → APPROVED / REJECTED / TIMEOUT 状态机
```

---

## 目录结构

```
项目根/
  ├── src/
  │   └── harness/
  │       ├── __init__.py        # 包导出
  │       ├── action.py          # 数据模型 (Action, ActionResult, 枚举)
  │       ├── agent.py           # Agent 主循环
  │       ├── cli.py             # CLI 入口 (setup/status/run/config)
  │       ├── config.py          # YAML 配置加载
  │       ├── credential.py      # 凭据管理 (OS Keyring / 文件回退)
  │       ├── feedback.py        # 反馈闭环 (校验器+分类器+重试)
  │       ├── guardrail.py       # 治理护栏 (RuleEngine+Sandbox+HITLGate)
  │       ├── llm.py             # LLM 抽象层 (OpenAILLM + MockLLM)
  │       ├── memory.py          # 上下文与记忆 (会话历史+知识存储)
  │       └── tools.py           # 工具执行器 (read/write/edit/shell)
  ├── tests/
  │   ├── unit/                  # 单元测试 (91 个)
  │   │   ├── test_action.py
  │   │   ├── test_agent.py
  │   │   ├── test_cli.py
  │   │   ├── test_config.py
  │   │   ├── test_credential.py
  │   │   ├── test_feedback.py
  │   │   ├── test_guardrail.py
  │   │   ├── test_llm.py
  │   │   ├── test_memory.py
  │   │   └── test_tools.py
  │   └── integration/
  │       └── test_demo.py       # 机制演示 (3 个场景, 11 个测试)
  ├── Dockerfile                 # Docker 容器化
  ├── .gitlab-ci.yml             # CI 配置 (unit-test + integration-test + docker-build)
  ├── pyproject.toml             # Python 项目配置
  ├── .gitignore
  ├── .dockerignore
  ├── SPEC.md                    # 设计规约
  ├── PLAN.md                    # 实现计划
  ├── SPEC_PROCESS.md            # 开发过程记录
  ├── AGENT_LOG.md               # Agent 日志
  └── REFLECTION.md              # 反思报告
```

---

## 安装

### 前提条件

- Python 3.12+
- pip

### 从源码安装

```bash
# 克隆仓库
git clone https://github.com/CXY0923/AI-SE.git
cd AI-SE

# 创建虚拟环境（推荐）
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"
```

### 通过 Docker 运行

```bash
# 构建镜像
docker build -t coding-agent-harness .

# 运行
docker run --rm -v harness-data:/root/.harness coding-agent-harness --help
```

---

## 运行

### 1. 配置 API Key

首次使用需要安全录入 OpenAI API Key：

```bash
# 从源码安装后
harness setup

# 通过 Docker
docker run -it -v harness-data:/root/.harness coding-agent-harness setup
```

Key 通过操作系统钥匙串安全存储（Windows Credential Manager / macOS Keychain / Linux Secret Service），不会明文写入任何文件。

### 2. 查看状态

```bash
harness status
```

显示配置状态，**不会回显明文 Key**。

### 3. 运行任务

```bash
harness run "读取 main.py 并运行测试"
```

### 4. 运行测试

```bash
# 全部测试
pytest -v

# 仅单元测试
pytest tests/unit/ -v

# 仅集成测试（机制演示）
pytest tests/integration/ -v

# 指定模块测试
pytest tests/unit/test_guardrail.py -v
```

---

## 配置

配置文件位于 `~/.harness/config.yaml`（自动创建）：

```yaml
harness:
  max_rounds: 20
  llm:
    provider: openai
    base_url: https://api.openai.com/v1    # 可自定义（如 vLLM / ollama 兼容端点）
    model: gpt-4o                           # 可自定义
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
    allow_commands: [git, npm, python, pytest, cat, ls, mkdir, cp, echo]
  feedback:
    max_retries: 3
```

---

## 分发

### Docker 容器（推荐）

```bash
# 构建
docker build -t coding-agent-harness .

# 运行任务（挂载当前目录为工作区）
docker run -it --rm \
  -v harness-data:/root/.harness \
  -v $(pwd):/workspace -w /workspace \
  coding-agent-harness run "修复失败的测试"

# 首次配置 Key
docker run -it --rm \
  -v harness-data:/root/.harness \
  coding-agent-harness setup
```

### CI/CD

`.gitlab-ci.yml` 包含三个 job：

| Job | 说明 |
|------|------|
| `unit-test` | 运行单元测试 |
| `integration-test` | 运行集成测试 |
| `docker-build` | 构建 Docker 镜像并保存为 tar.gz |

---

## 安全边界

### 凭据安全

| 威胁 | 风险等级 | 对策 |
|------|---------|------|
| API Key 硬编码在源码中 | **高** | 源码中无任何凭据占位符 |
| API Key 出现在 Git 历史中 | **高** | `.gitignore` 排除 `.env`、`*.key`、`credentials*` |
| API Key 出现在日志中 | **中** | 日志中屏蔽 key 输出 |
| 操作系统钥匙串被破解 | **低** | 依赖 OS 级别安全机制 |

### 治理护栏（三层保护）

```
                    ┌─────────────────────┐
                    │   Action 进入护栏    │
                    └─────────┬───────────┘
                              │
              ┌───────────────▼────────────────┐
              │   Layer 1: 规则引擎 (RuleEngine) │  ← 黑名单/需审批规则
              │   fnmatch 通配符匹配，O(1) 判断   │
              └───────────────┬────────────────┘
                              │
              ┌───────────────▼────────────────┐
              │   Layer 2: 沙箱边界 (Sandbox)    │  ← 路径逃逸检测
              │   os.path.realpath() 解析后检查   │  ← 命令白名单
              └───────────────┬────────────────┘
                              │
              ┌───────────────▼────────────────┐
              │   Layer 3: HITL 审批 (HITLGate)  │  ← 人工介入
              │   状态机: PENDING→APPROVED/      │
              │          REJECTED/TIMEOUT       │
              └───────────────┬────────────────┘
                              │
                    ┌─────────▼───────────┐
                    │  最终裁决 Decision    │
                    │  ALLOW / DENY / HITL │
                    └─────────────────────┘
```

- **所有护栏机制都是确定性代码**，不依赖 LLM 判断
- 每条规则可以独立测试，移除 LLM 后仍可验证
- HITL 审批有超时保护（默认 5 分钟），超时自动拒绝

### 已配置的护栏规则

| 规则 | 类型 | 效果 |
|------|------|------|
| `rm -rf /` | DENY | 禁止删除根目录 |
| 路径逃逸 | DENY | 禁止访问工作目录外的文件 |
| 未在白名单的命令 | DENY | 仅允许 `git, python, pytest, cat, ls, mkdir, cp, echo` |
| `git push` | PENDING | 推送代码需人工确认 |

---

## 技术栈

| 组件 | 选择 |
|------|------|
| 语言 | Python 3.12+ |
| LLM 接口 | OpenAI 兼容格式（支持自定义 base_url + model） |
| 凭据管理 | OS Keyring（`keyring` 库），回退到加密文件 |
| 测试框架 | pytest |
| 配置格式 | YAML |
| 分发 | Docker 容器 |
| 构建工具 | hatchling |

---

## 仓库

- GitHub: [https://github.com/CXY0923/AI-SE](https://github.com/CXY0923/AI-SE)
- NJU GitLab: _（待补充）_

---

## 许可证

本项目为 AI4SE 课程期末项目，仅供学习参考。