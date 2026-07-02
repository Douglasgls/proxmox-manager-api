from datetime import datetime

from app.integrations.proxmox.container_session import ContainerSession
from app.integrations.proxmox.models import CommandResult
from app.integrations.proxmox.proxmox_client import ProxmoxClient


class FakeProxmoxClient:
    def exec(
        self,
        container_id: int,
        command: str,
    ) -> CommandResult:
        return CommandResult(
            success=True,
            command=command,
            stdout=f"container={container_id}",
            stderr="",
            exit_code=0,
            duration=0.01,
            executed_at=datetime.now(),
        )


client = ProxmoxClient()
session = ContainerSession(
    proxmox_client=client,
    container_id=101,
)

result = session.exec(
    "ls -la"
)

# results = session.exec_many(
#     [
#         "apt update",
#         "apt install curl -y",
#     ]
# )

print(result)
# print(results)
