import unittest
from unittest.mock import MagicMock, patch
from app.integrations.proxmox.proxmox_client import ProxmoxClient
from app.integrations.proxmox.exceptions import ProxmoxAPIError

class ProxmoxClientStorageTests(unittest.TestCase):

    @patch('app.integrations.proxmox.proxmox_client.load_dotenv')
    @patch('app.integrations.proxmox.proxmox_client.ShellExecutor')
    def setUp(self, mock_shell_executor, mock_load_dotenv):
        self.client = ProxmoxClient()

    def test_storage_supports_containers(self):
        # Case 1: Storage with rootdir supports containers
        storage_thin = {"storage": "local-lvm", "content": "images,rootdir"}
        self.assertTrue(self.client._storage_supports_containers(storage_thin))

        # Case 2: Storage without rootdir does not support containers
        storage_dir = {"storage": "local", "content": "iso,vztmpl,backup"}
        self.assertFalse(self.client._storage_supports_containers(storage_dir))

        # Case 3: Storage with empty/no content defaults to True (standard fallback)
        storage_empty = {"storage": "custom"}
        self.assertTrue(self.client._storage_supports_containers(storage_empty))

    @patch.object(ProxmoxClient, 'list_storage')
    def test_first_storage_id_prioritizes_rootdir(self, mock_list_storage):
        # Case 1: local-lvm comes second in list
        mock_list_storage.return_value = [
            {"storage": "local", "content": "iso,vztmpl,backup"},
            {"storage": "local-lvm", "content": "images,rootdir"}
        ]
        self.assertEqual(self.client._first_storage_id(), "local-lvm")

        # Case 2: local-lvm comes first in list
        mock_list_storage.return_value = [
            {"storage": "local-lvm", "content": "images,rootdir"},
            {"storage": "local", "content": "iso,vztmpl,backup"}
        ]
        self.assertEqual(self.client._first_storage_id(), "local-lvm")

        # Case 3: No storage explicitly supports rootdir, fall back to the first available
        mock_list_storage.return_value = [
            {"storage": "local", "content": "iso,vztmpl,backup"},
            {"storage": "backup-only", "content": "backup"}
        ]
        self.assertEqual(self.client._first_storage_id(), "local")

        # Case 4: No storages found at all
        mock_list_storage.return_value = []
        with self.assertRaises(ProxmoxAPIError):
            self.client._first_storage_id()

if __name__ == "__main__":
    unittest.main()
