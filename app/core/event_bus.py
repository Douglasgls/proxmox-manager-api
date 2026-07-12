import asyncio
import logging
from typing import Dict, Set, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class Subscriber:
    async def send(self, data: dict):
        raise NotImplementedError

class WebSocketSubscriber(Subscriber):
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def send(self, data: dict):
        await self.websocket.send_json(data)

class QueueSubscriber(Subscriber):
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.queue = queue
        self.loop = loop

    async def send(self, data: dict):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.queue.put_nowait, data)
        else:
            self.queue.put_nowait(data)

class EventBus:
    def __init__(self):
        # Maps channel name (str) to a set of Subscriber objects
        self._channels: Dict[str, Set[Subscriber]] = {}

    def register(self, channel: str, subscriber: Subscriber):
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(subscriber)
        logger.debug(f"Registered subscriber to channel: {channel}. Total subscribers: {len(self._channels[channel])}")

    def unregister(self, channel: str, subscriber: Subscriber):
        if channel in self._channels:
            self._channels[channel].discard(subscriber)
            logger.debug(f"Unregistered subscriber from channel: {channel}. Remaining subscribers: {len(self._channels[channel])}")
            if not self._channels[channel]:
                del self._channels[channel]

    def unregister_from_all(self, subscriber: Subscriber):
        for channel in list(self._channels.keys()):
            if subscriber in self._channels[channel]:
                self._channels[channel].discard(subscriber)
                logger.debug(f"Unregistered subscriber from channel: {channel} (bulk unregister)")
                if not self._channels[channel]:
                    del self._channels[channel]

    async def publish(self, channel: str, data: dict):
        subscribers = list(self._channels.get(channel, []))
        if not subscribers:
            return
        
        # Publish concurrently
        tasks = []
        for subscriber in subscribers:
            tasks.append(self._safe_send(subscriber, channel, data))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_send(self, subscriber: Subscriber, channel: str, data: dict):
        try:
            await subscriber.send(data)
        except Exception as e:
            logger.debug(f"Failed to send message to subscriber on channel {channel}: {e}")
            # Self-heal/remove failed subscriber
            self.unregister(channel, subscriber)

    async def broadcast(self, data: dict):
        all_subscribers = set()
        for subs in self._channels.values():
            all_subscribers.update(subs)
        
        if not all_subscribers:
            return
            
        tasks = []
        for subscriber in all_subscribers:
            # We don't have a specific channel, so we pass '*' for logging/cleanup
            tasks.append(self._safe_send(subscriber, "*", data))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

event_bus = EventBus()
