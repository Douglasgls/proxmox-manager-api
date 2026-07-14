import asyncio
from typing import Any
from app.core.event_bus import event_bus

class JobEventManager:
    def __init__(self):
        self.loop = None

    def publish(
        self,
        job_id: str,
        event: dict[str, Any],
    ):
        print(f"[JobEvents DEBUG] publish chamado para job_id={job_id} com event={event.get('event')}. Status do Job={event.get('status')}")
        
        if self.loop and self.loop.is_running():
            print(f"[JobEvents DEBUG] Agendando publicação no loop principal de forma thread-safe...")
            asyncio.run_coroutine_threadsafe(
                event_bus.publish(f"jobs.{job_id}", event),
                self.loop
            )
            asyncio.run_coroutine_threadsafe(
                event_bus.publish("jobs", event),
                self.loop
            )
        else:
            print(f"[JobEvents DEBUG] Loop principal indisponível ou inativo. Tentando publicar no loop da thread atual...")
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    asyncio.create_task(event_bus.publish(f"jobs.{job_id}", event))
                    asyncio.create_task(event_bus.publish("jobs", event))
            except RuntimeError as e:
                print(f"[JobEvents DEBUG] Erro ao obter loop de eventos da thread atual: {e}")
                pass

job_event_manager = JobEventManager()

