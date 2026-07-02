from app.provision.engine import ProvisionEngine
from app.provision.plan import ProvisionPlan
from app.components.dummy_component import DummyComponent

plan = ProvisionPlan(
    name="Teste",
    description="Primeiro teste",
    components=[
        DummyComponent(),
        DummyComponent()
    ]
)

engine = ProvisionEngine()

result = engine.execute(plan)

print(result)