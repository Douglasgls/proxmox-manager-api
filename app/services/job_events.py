import asyncio
from typing import Any
from app.core.event_bus import event_bus, QueueSubscriber

class JobSubscriber:
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.queue = queue
        self.loop = loop

class JobEventManager:
    async def subscribe(
        self,
        job_id: str,
    ) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        subscriber = QueueSubscriber(
            queue=queue,
            loop=asyncio.get_running_loop(),
        )
        setattr(queue, "_subscriber_ref", subscriber)
        event_bus.register(f"jobs:{job_id}", subscriber)
        return queue

    def unsubscribe(
        self,
        job_id: str,
        queue: asyncio.Queue,
    ):
        subscriber = getattr(queue, "_subscriber_ref", None)
        if subscriber:
            event_bus.unregister(f"jobs:{job_id}", subscriber)

    def publish(
        self,
        job_id: str,
        event: dict[str, Any],
    ):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # Publish to specific job channel for old /jobs/{job_id}/stream
                asyncio.create_task(event_bus.publish(f"jobs:{job_id}", event))
                # Also publish to the general "jobs" channel for the new /ws channel
                asyncio.create_task(event_bus.publish("jobs", event))
        except RuntimeError:
            pass

job_event_manager = JobEventManager()

