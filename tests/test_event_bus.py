import unittest
import asyncio
from app.core.event_bus import EventBus, Subscriber

class MockSubscriber(Subscriber):
    def __init__(self):
        self.received_messages = []

    async def send(self, data: dict):
        self.received_messages.append(data)

class EventBusTests(unittest.IsolatedAsyncioTestCase):
    def test_register_and_unregister(self):
        bus = EventBus()
        sub = MockSubscriber()
        
        bus.register("test_channel", sub)
        self.assertIn("test_channel", bus._channels)
        self.assertIn(sub, bus._channels["test_channel"])
        
        bus.unregister("test_channel", sub)
        self.assertNotIn("test_channel", bus._channels)

    def test_unregister_from_all(self):
        bus = EventBus()
        sub = MockSubscriber()
        
        bus.register("channel_1", sub)
        bus.register("channel_2", sub)
        self.assertIn("channel_1", bus._channels)
        self.assertIn("channel_2", bus._channels)
        
        bus.unregister_from_all(sub)
        self.assertNotIn("channel_1", bus._channels)
        self.assertNotIn("channel_2", bus._channels)

    async def test_publish(self):
        bus = EventBus()
        sub1 = MockSubscriber()
        sub2 = MockSubscriber()
        
        bus.register("channel_1", sub1)
        bus.register("channel_2", sub2)
        
        await bus.publish("channel_1", {"message": "hello channel 1"})
        self.assertEqual(len(sub1.received_messages), 1)
        self.assertEqual(sub1.received_messages[0], {"message": "hello channel 1"})
        self.assertEqual(len(sub2.received_messages), 0)
        
        await bus.broadcast({"message": "hello all"})
        self.assertEqual(len(sub1.received_messages), 2)
        self.assertEqual(sub1.received_messages[1], {"message": "hello all"})
        self.assertEqual(len(sub2.received_messages), 1)
        self.assertEqual(sub2.received_messages[0], {"message": "hello all"})
