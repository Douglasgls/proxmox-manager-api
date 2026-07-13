import asyncio
import logging
import re
from typing import Dict

from app.core.event_bus import event_bus
from app.monitoring.publisher import MonitoringPublisher

logger = logging.getLogger(__name__)

# Constants for intervals (in seconds)
DASHBOARD_METRICS_INTERVAL = 2.0
HOST_METRICS_INTERVAL = 30.0
CONTAINERS_METRICS_INTERVAL = 3.0
CONTAINER_INDIVIDUAL_METRICS_INTERVAL = 1.0

CONTAINER_METRICS_PATTERN = re.compile(r"^containers\.(\d+)\.metrics$")

class MonitoringScheduler:
    """Scheduler that runs publisher tasks at defined intervals when subscribers exist."""

    def __init__(self, publisher: MonitoringPublisher):
        self.publisher = publisher
        self.running = False
        self._tasks = []

    async def start(self):
        """Start the background loops."""
        self.running = True
        logger.info("Starting MonitoringScheduler background tasks...")
        self._tasks = [
            asyncio.create_task(self._dashboard_loop()),
            asyncio.create_task(self._host_loop()),
            asyncio.create_task(self._containers_loop()),
            asyncio.create_task(self._individual_containers_loop()),
        ]

    async def stop(self):
        """Stop the background loops and cancel tasks."""
        self.running = False
        logger.info("Stopping MonitoringScheduler background tasks...")
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    async def _dashboard_loop(self):
        while self.running:
            try:
                if event_bus.has_subscribers("dashboard.metrics") or event_bus.has_subscribers("dashboard"):
                    await self.publisher.publish_dashboard_metrics()
                else:
                    logger.debug("Skipping dashboard metrics: no subscribers.")
            except Exception as e:
                logger.error(f"Error in dashboard loop: {e}", exc_info=True)
            await asyncio.sleep(DASHBOARD_METRICS_INTERVAL)

    async def _host_loop(self):
        while self.running:
            try:
                if event_bus.has_subscribers("host.metrics"):
                    await self.publisher.publish_host_metrics()
                else:
                    logger.debug("Skipping host metrics: no subscribers.")
            except Exception as e:
                logger.error(f"Error in host loop: {e}", exc_info=True)
            await asyncio.sleep(HOST_METRICS_INTERVAL)

    async def _containers_loop(self):
        while self.running:
            try:
                if event_bus.has_subscribers("containers.metrics") or event_bus.has_subscribers("containers"):
                    await self.publisher.publish_all_container_metrics()
                else:
                    logger.debug("Skipping containers metrics: no subscribers.")
            except Exception as e:
                logger.error(f"Error in containers loop: {e}", exc_info=True)
            await asyncio.sleep(CONTAINERS_METRICS_INTERVAL)


    async def _individual_containers_loop(self):
        while self.running:
            try:
                active_channels = event_bus.list_channels()
                subscribed_container_ids = []
                for channel in active_channels:
                    match = CONTAINER_METRICS_PATTERN.match(channel)
                    if match:
                        try:
                            container_id = int(match.group(1))
                            subscribed_container_ids.append(container_id)
                        except ValueError:
                            pass
                
                # For each subscribed container, publish its metrics
                if subscribed_container_ids:
                    tasks = [
                        self.publisher.publish_container_metrics(cid)
                        for cid in subscribed_container_ids
                    ]
                    await asyncio.gather(*tasks, return_exceptions=True)
                else:
                    logger.debug("No individual container metrics subscribers.")
            except Exception as e:
                logger.error(f"Error in individual containers loop: {e}", exc_info=True)
            await asyncio.sleep(CONTAINER_INDIVIDUAL_METRICS_INTERVAL)
