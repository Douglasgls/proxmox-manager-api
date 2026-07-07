import asyncio
from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from typing import Any


@dataclass
class JobSubscriber:
    queue: asyncio.Queue
    loop: asyncio.AbstractEventLoop


class JobEventManager:

    def __init__(
        self,
    ):
        self._subscribers: dict[str, list[JobSubscriber]] = defaultdict(list)

    async def subscribe(
        self,
        job_id: str,
    ) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[job_id].append(
            JobSubscriber(
                queue=queue,
                loop=asyncio.get_running_loop(),
            )
        )
        return queue

    def unsubscribe(
        self,
        job_id: str,
        queue: asyncio.Queue,
    ):
        subscribers = self._subscribers.get(
            job_id,
            []
        )

        for subscriber in copy(subscribers):
            if subscriber.queue == queue:
                subscribers.remove(
                    subscriber
                )
                break

        if not subscribers and job_id in self._subscribers:
            del self._subscribers[job_id]

    def publish(
        self,
        job_id: str,
        event: dict[str, Any],
    ):
        subscribers = copy(
            self._subscribers.get(
                job_id,
                []
            )
        )

        for queue in subscribers:
            if queue.loop.is_running():
                queue.loop.call_soon_threadsafe(
                    queue.queue.put_nowait,
                    event,
                )
            else:
                queue.queue.put_nowait(
                    event
                )


job_event_manager = JobEventManager()
