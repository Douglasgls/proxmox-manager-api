
from app.components.definition import ComponentDefinition
from app.provision.step import ProvisionStep


class ProvisionPlan:
    def __init__(
        self,
        name: str,
        description: str,
        components: list[ComponentDefinition] | None = None,
        steps: list[ProvisionStep] | None = None,
        id: str | None = None,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.components = list(components or [])
        self.steps = list(steps or [])

    def add_step(self, step: ProvisionStep):
        self.steps.append(step)

    def __repr__(self):
        return f"ProvisionPlan(name={self.name}, description={self.description}, components={self.components}, steps={self.steps})"

