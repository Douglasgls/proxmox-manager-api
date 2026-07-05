from app.components.definition import ComponentDefinition
from app.provision.engine import ProvisionEngine
from app.provision.plan import ProvisionPlan
from app.integrations.proxmox.container_session import CommandResult
from datetime import datetime

plan = ProvisionPlan(
    name="Teste",
    description="Primeiro teste",
    components=[
        ComponentDefinition(
            name="echo",
        )
    ],
)

class FakeSession:

    def exec(self, command: str):

        print(f"> {command}")

        return CommandResult(
            success=True,
            command=command,
            stdout="OK",
            stderr="",
            exit_code=0,
            duration=0.0,
            executed_at=datetime.now(),
        )

engine = ProvisionEngine()

result = engine.execute(plan,session=FakeSession())

print(result)