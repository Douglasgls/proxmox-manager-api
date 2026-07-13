import unittest
from unittest.mock import MagicMock
from datetime import datetime

from app.services.container_service import ContainerService
from app.models.container import Container
from app.integrations.proxmox import ContainerStatus, OperationResult
from app.dto.response.container import ContainerStatusDTO

class ContainerServiceTests(unittest.TestCase):

    def setUp(self):
        self.repository = MagicMock()
        self.proxmox_client = MagicMock()
        self.audit_log_service = MagicMock()
        self.service = ContainerService(
            repository=self.repository,
            proxmox_client=self.proxmox_client,
            audit_log_service=self.audit_log_service,
        )

    def test_sync_container_runtime(self):
        container = Container(
            id="test-uuid",
            container_number=100,
            name="test-container",
            status="stopped",
            ip_address=None
        )
        
        status_info = ContainerStatus(
            container_id=100,
            status="running",
            ip_address="192.168.1.50"
        )
        
        self.proxmox_client.get_container_status.return_value = status_info
        self.repository.update.side_effect = lambda c: c
        
        updated = self.service._sync_container_runtime(container)
        
        self.proxmox_client.get_container_status.assert_called_once_with(100)
        self.assertEqual(updated.status, "running")
        self.assertEqual(updated.ip_address, "192.168.1.50")
        self.repository.update.assert_called_once_with(container)

    def test_start_container_not_running(self):
        container = Container(
            id="test-uuid",
            container_number=100,
            name="test-container",
            status="stopped"
        )
        self.repository.get.return_value = container
        self.repository.update.side_effect = lambda c: c
        
        # Real status on Proxmox starts as stopped, then goes to running after operation
        status_stopped = ContainerStatus(container_id=100, status="stopped", ip_address=None)
        status_running = ContainerStatus(container_id=100, status="running", ip_address="192.168.1.50")
        
        self.proxmox_client.get_container_status.side_effect = [
            status_stopped,  # first sync
            status_running,  # wait loop check
            status_running,  # second sync
        ]
        
        op_result = OperationResult(
            container_id=100,
            operation="start",
            success=True,
            message="Started"
        )
        self.proxmox_client.start_container.return_value = op_result
        
        res = self.service.start("test-uuid")
        
        self.proxmox_client.start_container.assert_called_once_with(container_id=100)
        self.assertEqual(res.status, "running")
        self.assertTrue(res.success)
        self.assertEqual(container.status, "running")
        self.assertEqual(container.ip_address, "192.168.1.50")

    def test_start_container_already_running(self):
        container = Container(
            id="test-uuid",
            container_number=100,
            name="test-container",
            status="stopped" # stored status is stopped
        )
        self.repository.get.return_value = container
        
        # But Proxmox status is actually running!
        status_running = ContainerStatus(container_id=100, status="running", ip_address="192.168.1.50")
        self.proxmox_client.get_container_status.return_value = status_running
        self.repository.update.side_effect = lambda c: c
        
        with self.assertRaises(ValueError) as ctx:
            self.service.start("test-uuid")
            
        self.assertEqual(str(ctx.exception), "Container já iniciado")
        self.proxmox_client.start_container.assert_not_called()

    def test_stop_container_running(self):
        container = Container(
            id="test-uuid",
            container_number=100,
            name="test-container",
            status="running"
        )
        self.repository.get.return_value = container
        self.repository.update.side_effect = lambda c: c
        
        status_running = ContainerStatus(container_id=100, status="running", ip_address="192.168.1.50")
        status_stopped = ContainerStatus(container_id=100, status="stopped", ip_address=None)
        
        self.proxmox_client.get_container_status.side_effect = [
            status_running,  # first sync
            status_stopped,  # wait loop check
            status_stopped,  # second sync
        ]
        
        op_result = OperationResult(
            container_id=100,
            operation="stop",
            success=True,
            message="Stopped"
        )
        self.proxmox_client.stop_container.return_value = op_result
        
        res = self.service.stop("test-uuid")
        
        self.proxmox_client.stop_container.assert_called_once_with(100)
        self.assertEqual(res.status, "stopped")
        self.assertTrue(res.success)
        self.assertEqual(container.status, "stopped")

    def test_stop_container_already_stopped(self):
        container = Container(
            id="test-uuid",
            container_number=100,
            name="test-container",
            status="running" # stored status is running
        )
        self.repository.get.return_value = container
        
        # But Proxmox status is actually stopped!
        status_stopped = ContainerStatus(container_id=100, status="stopped", ip_address=None)
        self.proxmox_client.get_container_status.return_value = status_stopped
        self.repository.update.side_effect = lambda c: c
        
        with self.assertRaises(ValueError) as ctx:
            self.service.stop("test-uuid")
            
        self.assertEqual(str(ctx.exception), "Container já parado")
        self.proxmox_client.stop_container.assert_not_called()

    def test_get_status_uses_proxmox_only(self):
        container = Container(
            id="test-uuid",
            container_number=100,
            name="test-container",
            status="stopped" # stored is stopped
        )
        self.repository.get.return_value = container
        self.repository.update.side_effect = lambda c: c
        
        status_info = ContainerStatus(
            container_id=100,
            status="running",
            uptime_seconds=5000,
            cpu_usage_percent=12.5,
            memory_usage_mb=256,
            ip_address="192.168.1.75"
        )
        self.proxmox_client.get_container_status.return_value = status_info
        
        res = self.service.get_status("test-uuid")
        
        self.assertEqual(res.status, "running")
        self.assertEqual(res.proxmox_status, "running")
        self.assertEqual(res.uptime_seconds, 5000)
        self.assertEqual(res.cpu_usage_percent, 12.5)
        self.assertEqual(res.memory_usage_mb, 256)
        
        # Verify db was synced
        self.assertEqual(container.status, "running")
        self.assertEqual(container.ip_address, "192.168.1.75")
        self.repository.update.assert_called_once()
