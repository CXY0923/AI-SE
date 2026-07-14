import os
import subprocess
from harness.action import Action, ActionResult


class ToolExecutor:
    def __init__(self, work_dir: str = "."):
        self.work_dir = os.path.abspath(work_dir)

    def execute(self, action: Action) -> ActionResult:
        handlers = {
            "read": self._read,
            "write": self._write,
            "edit": self._edit,
            "shell": self._shell,
            "run_test": self._shell,
        }
        handler = handlers.get(action.type)
        if handler is None:
            return ActionResult(success=False, exit_code=1, stderr=f"Unknown action type: {action.type}")
        return handler(action.params)

    def _resolve_path(self, path: str) -> str:
        if not os.path.isabs(path):
            path = os.path.join(self.work_dir, path)
        return os.path.realpath(path)

    def _read(self, params: dict) -> ActionResult:
        path = self._resolve_path(params["path"])
        try:
            with open(path) as f:
                content = f.read()
            return ActionResult(success=True, stdout=content)
        except FileNotFoundError:
            return ActionResult(success=False, exit_code=1, stderr=f"File not found: {path}")

    def _write(self, params: dict) -> ActionResult:
        path = self._resolve_path(params["path"])
        content = params.get("content", "")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return ActionResult(success=True, output_path=path)

    def _edit(self, params: dict) -> ActionResult:
        path = self._resolve_path(params["path"])
        old_str = params["old_str"]
        new_str = params["new_str"]
        try:
            with open(path) as f:
                content = f.read()
            if old_str not in content:
                return ActionResult(success=False, exit_code=1, stderr="Pattern not found in file")
            new_content = content.replace(old_str, new_str, 1)
            with open(path, "w") as f:
                f.write(new_content)
            return ActionResult(success=True)
        except FileNotFoundError:
            return ActionResult(success=False, exit_code=1, stderr=f"File not found: {path}")

    def _shell(self, params: dict) -> ActionResult:
        command = params["command"]
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.work_dir,
            )
            return ActionResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return ActionResult(success=False, exit_code=124, stderr="Command timed out")