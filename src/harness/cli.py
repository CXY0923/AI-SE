import argparse
import getpass
import sys
import os

from harness.credential import CredentialManager
from harness.config import load_config
from harness.action import Action


def setup_command():
    cred = CredentialManager()
    print("Coding Agent Harness - 首次配置")
    print("=" * 40)

    if cred.has_key("openai"):
        print("OpenAI API Key 已配置。")
        override = input("是否覆盖？(y/N): ").strip().lower()
        if override != "y":
            print("保留现有配置。")
            return

    key = getpass.getpass("请输入 OpenAI API Key (输入将被隐藏): ")
    if not key.strip():
        print("Key 不能为空。")
        sys.exit(1)

    cred.store_key("openai", key)
    print("✅ API Key 已安全存储到系统钥匙串。")


def status_command():
    cred = CredentialManager()
    loaded = False
    services = cred.list_services()

    print("Coding Agent Harness - 状态")
    print("=" * 40)

    if services:
        print(f"✅ 已配置的服务: {', '.join(services)}")
        loaded = True
    else:
        print("❌ 未配置 API Key。运行 `harness setup` 配置。")

    config_path = os.path.expanduser("~/.harness/config.yaml")
    if os.path.exists(config_path):
        print(f"✅ 配置文件: {config_path}")
        loaded = True
    else:
        print("ℹ️  配置文件不存在，将使用默认配置。")

    if loaded:
        print("✅ Harness 已就绪。")
    else:
        print("❌ 请先运行 `harness setup` 配置 API Key。")


def run_command(args):
    from harness.llm import OpenAILLM
    from harness.tools import ToolExecutor
    from harness.guardrail import RuleEngine, Sandbox, HITLGate, Guardrail
    from harness.feedback import FeedbackLoop
    from harness.memory import Memory
    from harness.agent import AgentHarness

    config = load_config()
    cred = CredentialManager()
    api_key = cred.get_key("openai")
    if not api_key:
        print("❌ API Key 未配置。请先运行 `harness setup`。")
        sys.exit(1)

    llm = OpenAILLM(
        api_key=api_key,
        model=config.llm_model,
        base_url=config.llm_base_url,
        temperature=config.llm_temperature,
    )
    tools = ToolExecutor(work_dir=config.sandbox_work_dir)
    rule_engine = RuleEngine()
    sandbox = Sandbox(
        work_dir=config.sandbox_work_dir,
        allow_commands=config.sandbox_allow_commands,
    )
    hitl = HITLGate(timeout=config.hitl_timeout)
    guardrail = Guardrail(rule_engine=rule_engine, sandbox=sandbox, hitl=hitl)
    feedback = FeedbackLoop(max_retries=config.feedback_max_retries)
    memory = Memory()

    agent = AgentHarness(
        llm=llm,
        tools=tools,
        guardrail=guardrail,
        feedback=feedback,
        memory=memory,
        config=config,
        max_rounds=config.max_rounds,
    )
    task = " ".join(args.task) if args.task else ""
    if not task:
        print("❌ 请提供任务描述。")
        sys.exit(1)

    print(f"🚀 开始任务: {task}")
    result = agent.run(task)
    if result["success"]:
        print(f"✅ 任务完成 ({result['rounds']} 轮)")
    else:
        print(f"❌ 任务失败: {result['reason']} ({result['rounds']} 轮)")


def get_hitl_gate():
    from harness.guardrail import HITLGate
    return HITLGate(timeout=300)


def approve_command():
    gate = get_hitl_gate()
    pending = gate.list_pending()

    if not pending:
        print("✅ 没有待审批的请求。")
        return

    print(f"📋 待审批请求 ({len(pending)} 个):")
    print("=" * 60)
    for i, p in enumerate(pending, 1):
        print(f"{i}. [{p['id']}] {p['action_type']}")
        print(f"   参数: {p['params']}")
        if p.get('thought'):
            print(f"   思考: {p['thought']}")
        print()

    try:
        choice = input("选择要审批的编号 (输入编号，或按 Enter 跳过): ").strip()
        if not choice:
            print("已跳过。")
            return

        idx = int(choice) - 1
        if idx < 0 or idx >= len(pending):
            print("无效编号。")
            return

        selected = pending[idx]
        action = Action(
            type=selected["action_type"],
            params=selected["params"],
            thought=selected.get("thought", ""),
        )

        cmd = input("审批 (a)pprove / (r)eject / (s)kip? [a]: ").strip().lower()
        if cmd == "r" or cmd == "reject":
            result = gate.reject(action)
            print(f"❌ 已拒绝: {result.reason}")
        else:
            result = gate.approve(action)
            print(f"✅ 已批准: {result.reason}")
    except (ValueError, IndexError):
        print("输入无效。")


def config_command():
    config_path = os.path.expanduser("~/.harness/config.yaml")
    if os.path.exists(config_path):
        with open(config_path) as f:
            print(f.read())
    else:
        print("配置文件不存在，使用默认配置。")
        print("创建 ~/.harness/config.yaml 进行自定义配置。")


def main():
    parser = argparse.ArgumentParser(description="Coding Agent Harness")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("setup", help="安全配置 API Key")
    subparsers.add_parser("status", help="查看配置状态")
    subparsers.add_parser("config", help="查看配置")

    subparsers.add_parser("approve", help="查看和审批待处理的请求")

    run_parser = subparsers.add_parser("run", help="运行编码任务")
    run_parser.add_argument("task", nargs=argparse.REMAINDER, help="任务描述")

    args = parser.parse_args()

    if args.command == "setup":
        setup_command()
    elif args.command == "status":
        status_command()
    elif args.command == "run":
        run_command(args)
    elif args.command == "approve":
        approve_command()
    elif args.command == "config":
        config_command()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()