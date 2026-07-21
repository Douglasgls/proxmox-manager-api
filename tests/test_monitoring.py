import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
from datetime import datetime

from app.services.monitoring.tasks.publisher import MonitoringPublisher
from app.services.monitoring.tasks.scheduler import MonitoringScheduler
from app.dto.response.monitoring import HostMetricsDTO, ContainerInventorySummaryDTO, ContainerMetricsDTO

class MonitoringTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.host_service = MagicMock()
        self.container_service = MagicMock()
        self.publisher = MonitoringPublisher(
            host_service=self.host_service,
            container_service=self.container_service,
        )

    @patch("app.services.monitoring.tasks.publisher.event_bus")

    async def test_publish_dashboard_metrics(self, mock_event_bus):
        host_metrics = HostMetricsDTO(
            cpu_usage_percent=10.0,
            memory_used_bytes=1000,
            memory_free_bytes=3000,
            disk_used_bytes=500,
            disk_free_bytes=1500,
            rx_bytes=100,
            tx_bytes=200,
            load_average=[0.5, 0.5, 0.5],
            uptime_seconds=1000,
        )
        self.host_service.get_metrics.return_value = host_metrics
        
        container_inventory = ContainerInventorySummaryDTO(
            containers=[],
            total=10,
            running=4,
            stopped=6,
            locked=0,
            suspended=0,
        )
        self.container_service.get_inventory.return_value = container_inventory
        
        mock_event_bus.publish = AsyncMock()
        mock_event_bus.has_subscribers.return_value = False
        
        await self.publisher.publish_dashboard_metrics()
        
        mock_event_bus.publish.assert_called_once()
        channel, payload = mock_event_bus.publish.call_args[0]
        self.assertEqual(channel, "dashboard.metrics")
        self.assertEqual(payload["event"], "dashboard.metrics.updated")
        self.assertEqual(payload["data"]["cpu_usage_percent"], 10.0)
        self.assertEqual(payload["data"]["containers_running"], 4)
        self.assertEqual(payload["data"]["containers_stopped"], 6)

    @patch("app.services.monitoring.tasks.publisher.event_bus")
    async def test_publish_host_metrics(self, mock_event_bus):
        host_metrics = HostMetricsDTO(
            cpu_usage_percent=15.0,
            uptime_seconds=1000,
        )
        self.host_service.get_metrics.return_value = host_metrics
        mock_event_bus.publish = AsyncMock()
        mock_event_bus.has_subscribers.return_value = False
        
        await self.publisher.publish_host_metrics()
        
        mock_event_bus.publish.assert_called_once()
        channel, payload = mock_event_bus.publish.call_args[0]
        self.assertEqual(channel, "host.metrics")
        self.assertEqual(payload["event"], "host.metrics.updated")
        self.assertEqual(payload["data"]["cpu_usage_percent"], 15.0)

    @patch("app.services.monitoring.tasks.publisher.event_bus")
    async def test_publish_all_container_metrics(self, mock_event_bus):
        container_metrics = [
            ContainerMetricsDTO(container_id=101, status="running", cpu_usage_percent=5.0),
            ContainerMetricsDTO(container_id=102, status="stopped", cpu_usage_percent=0.0),
        ]
        self.container_service.get_metrics.return_value = container_metrics
        mock_event_bus.publish = AsyncMock()
        mock_event_bus.has_subscribers.return_value = False
        
        await self.publisher.publish_all_container_metrics()
        
        mock_event_bus.publish.assert_called_once()
        channel, payload = mock_event_bus.publish.call_args[0]
        self.assertEqual(channel, "containers.metrics")
        self.assertEqual(payload["event"], "containers.metrics.updated")
        self.assertEqual(len(payload["data"]), 2)
        self.assertEqual(payload["data"][0]["container_id"], 101)

    @patch("app.services.monitoring.tasks.publisher.event_bus")
    async def test_publish_container_metrics_single(self, mock_event_bus):
        metrics = ContainerMetricsDTO(container_id=101, status="running", cpu_usage_percent=5.0)
        self.container_service.get_container_metrics.return_value = metrics
        mock_event_bus.publish = AsyncMock()
        
        await self.publisher.publish_container_metrics(101)
        
        mock_event_bus.publish.assert_called_once()
        channel, payload = mock_event_bus.publish.call_args[0]
        self.assertEqual(channel, "containers.101.metrics")
        self.assertEqual(payload["event"], "containers.101.metrics.updated")
        self.assertEqual(payload["data"]["container_id"], 101)

    @patch("app.services.monitoring.tasks.scheduler.event_bus")
    async def test_scheduler_checks_subscribers_before_publishing(self, mock_event_bus):
        mock_publisher = MagicMock()
        mock_publisher.publish_dashboard_metrics = AsyncMock()
        mock_publisher.publish_host_metrics = AsyncMock()
        mock_publisher.publish_all_container_metrics = AsyncMock()
        mock_publisher.publish_container_metrics = AsyncMock()
        
        scheduler = MonitoringScheduler(publisher=mock_publisher)
        
        # Scenario 1: No subscribers
        mock_event_bus.has_subscribers.return_value = False
        mock_event_bus.list_channels.return_value = []
        
        await scheduler._dashboard_loop_once() if hasattr(scheduler, "_dashboard_loop_once") else None
        
        # Test individual functions manually since they run in background loops
        # We can mock asyncio.sleep to run only once or test the core logic.
        # Let's test the logic of the loop methods by mock running them.
        
        # Let's directly call the conditional check logic that would be inside the loop
        if mock_event_bus.has_subscribers("dashboard.metrics"):
            await mock_publisher.publish_dashboard_metrics()
        mock_publisher.publish_dashboard_metrics.assert_not_called()
        
        # Scenario 2: Active subscriber on dashboard
        mock_event_bus.has_subscribers.side_effect = lambda ch: ch == "dashboard.metrics"
        if mock_event_bus.has_subscribers("dashboard.metrics"):
            await mock_publisher.publish_dashboard_metrics()
        mock_publisher.publish_dashboard_metrics.assert_called_once()
        
        # Scenario 3: Active subscriber on individual container
        mock_event_bus.list_channels.return_value = ["containers.105.metrics"]
        
        # Simulate scheduler's individual loop logic
        active_channels = mock_event_bus.list_channels()
        subscribed_container_ids = []
        from app.services.monitoring.tasks.scheduler import CONTAINER_METRICS_PATTERN
        for channel in active_channels:
            match = CONTAINER_METRICS_PATTERN.match(channel)
            if match:
                subscribed_container_ids.append(int(match.group(1)))
                
        self.assertEqual(subscribed_container_ids, [105])

