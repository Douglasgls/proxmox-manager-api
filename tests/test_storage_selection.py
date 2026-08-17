import unittest
from unittest.mock import MagicMock, patch

from app.dto.request.create_container import CreateContainerDTO
from app.dto.response.monitoring import StorageInventoryDTO
from app.services.monitoring.collectors.inventory.storage_inventory_collector import StorageInventoryCollector
from app.services.container_creation_workflow import ContainerCreationWorkflow


class TestStorageSelection(unittest.TestCase):

    def test_storage_inventory_collector_maps_used_and_avail_bytes(self):
        mock_proxmox_client = MagicMock()
        mock_proxmox_client.list_storage.return_value = [
            {
                "storage": "local-lvm",
                "type": "lvmthin",
                "active": 1,
                "disable": 0,
                "shared": 0,
                "content": "rootdir,images",
                "total": 100000000000,
                "used": 20000000000,
                "avail": 80000000000,
            },
            {
                "storage": "disco-secundario",
                "type": "dir",
                "active": 1,
                "disable": 0,
                "shared": 0,
                "content": "rootdir",
                "total": 500000000000,
                "used": 50000000000,
                "avail": 450000000000,
            },
        ]

        collector = StorageInventoryCollector(mock_proxmox_client)
        result = collector.collect()

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], StorageInventoryDTO)
        self.assertEqual(result[0].name, "local-lvm")
        self.assertEqual(result[0].total_bytes, 100000000000)
        self.assertEqual(result[0].used_bytes, 20000000000)
        self.assertEqual(result[0].avail_bytes, 80000000000)

        self.assertEqual(result[1].name, "disco-secundario")
        self.assertEqual(result[1].total_bytes, 500000000000)
        self.assertEqual(result[1].used_bytes, 50000000000)
        self.assertEqual(result[1].avail_bytes, 450000000000)

    def test_create_container_dto_accepts_storage(self):
        dto = CreateContainerDTO(
            name="test-container",
            password="secretpassword",
            cpu=2,
            memory_mb=1024,
            disk_gb=10,
            storage="disco-secundario",
        )
        self.assertEqual(dto.storage, "disco-secundario")

    def test_workflow_passes_storage_to_container_service(self):
        mock_job_service = MagicMock()
        mock_container_service = MagicMock()
        mock_component_service = MagicMock()

        mock_container = MagicMock()
        mock_container.name = "test-container"
        mock_container_service.create.return_value = mock_container
        mock_component_service.validate_and_resolve_slugs.return_value = []

        workflow = ContainerCreationWorkflow(
            job_service=mock_job_service,
            container_service=mock_container_service,
            component_service=mock_component_service,
        )

        dto = CreateContainerDTO(
            name="test-container",
            password="secretpassword",
            cpu=1,
            memory_mb=512,
            disk_gb=5,
            storage="disco-extra",
        )

        workflow.run(job_id="job-123", dto=dto)

        mock_container_service.create.assert_called_once()
        kwargs = mock_container_service.create.call_args.kwargs
        self.assertEqual(kwargs.get("storage"), "disco-extra")


if __name__ == "__main__":
    unittest.main()

