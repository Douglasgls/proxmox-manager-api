import subprocess

from app.integrations.proxmox.exceptions import ShellExecutionError
from app.integrations.proxmox.models import ShellResult


class ShellExecutor:

    def __init__(
        self,
        timeout: int = 30,
    ):
        self.timeout = timeout

    def run(
        self,
        command: list[str],
        timeout: int | None = None,
    ) -> ShellResult:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=timeout or self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise ShellExecutionError(
                f"Command timed out: {' '.join(command)}"
            ) from exc
        except OSError as exc:
            raise ShellExecutionError(
                f"Command failed to start: {' '.join(command)}"
            ) from exc

        result = ShellResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
            success=completed.returncode == 0,
        )

        if not result.success:
            raise ShellExecutionError(
                result.stderr
                or result.stdout
                or f"Command failed: {' '.join(command)}",
                result=result,
            )

        return result

    def pct(
        self,
        *args,
        timeout: int | None = None,
    ) -> ShellResult:
        return self.run(
            ["pct", *[str(arg) for arg in args]],
            timeout=timeout,
        )

    def pvesh(
        self,
        *args,
        timeout: int | None = None,
    ) -> ShellResult:
        return self.run(
            ["pvesh", *[str(arg) for arg in args]],
            timeout=timeout,
        )

    def qm(
        self,
        *args,
        timeout: int | None = None,
    ) -> ShellResult:
        return self.run(
            ["qm", *[str(arg) for arg in args]],
            timeout=timeout,
        )
