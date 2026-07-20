import unittest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from app.core.event_bus import InternalEventBus, EnvironmentChanged
from app.cloud.publisher import EnvironmentChangedPublisher


class TestEvent:
    pass


class EnvironmentChangedTests(unittest.IsolatedAsyncioTestCase):

    def test_internal_event_bus_subscribe_publish(self):
        bus = InternalEventBus()
        received_events = []

        def callback(event):
            received_events.append(event)

        bus.subscribe(TestEvent, callback)
        
        event1 = TestEvent()
        bus.publish(event1)

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0], event1)

        # Non-subscribed event type shouldn't trigger callback
        class OtherEvent:
            pass
        bus.publish(OtherEvent())
        self.assertEqual(len(received_events), 1)

    async def test_publisher_debounce_and_message_format(self):
        # Mock Connection Manager
        connection_manager = MagicMock()
        connection_manager.send_message = AsyncMock()

        # Instantiate publisher with mock
        publisher = EnvironmentChangedPublisher(connection_manager)

        # Force a fresh event bus listener registry for testing
        from app.core.event_bus import internal_event_bus
        internal_event_bus._listeners[EnvironmentChanged] = [publisher.handle_environment_changed]

        # Publish EnvironmentChanged
        internal_event_bus.publish(EnvironmentChanged())

        # Debounce is active, self._pending_task is not None
        self.assertIsNotNone(publisher._pending_task)
        self.assertFalse(publisher._pending_task.done())

        # Publish multiple times, should be ignored
        internal_event_bus.publish(EnvironmentChanged())
        internal_event_bus.publish(EnvironmentChanged())

        # Wait for the debounce delay (2 seconds). We will await the pending task to finish.
        await publisher._pending_task

        # Verify that send_message was called exactly once
        connection_manager.send_message.assert_called_once()
        
        # Verify JSON message format
        called_arg = connection_manager.send_message.call_args[0][0]
        data = json.loads(called_arg)
        self.assertEqual(data["origin"], "agent")
        self.assertEqual(data["type"], "environment.changed")
        self.assertEqual(data["payload"], {})

        # Debounce should be reset (pending task is None)
        self.assertIsNone(publisher._pending_task)

        # Triggering again should schedule a new dispatch
        connection_manager.send_message.reset_mock()
        internal_event_bus.publish(EnvironmentChanged())
        self.assertIsNotNone(publisher._pending_task)
        await publisher._pending_task
        connection_manager.send_message.assert_called_once()
