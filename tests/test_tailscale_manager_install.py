import unittest
from unittest.mock import MagicMock

from app.components.tailscale_component import TailscaleComponent
from app.components.registry import ComponentRegistry
from app.components.definition import ComponentDefinition


class TestTailscaleComponentLifecycle(unittest.TestCase):

    def test_tailscale_component_has_install_and_validate(self):
        comp = TailscaleComponent()
        self.assertTrue(hasattr(comp, "install"))
        self.assertTrue(hasattr(comp, "validate"))

        mock_session = MagicMock()
        mock_res = MagicMock(exit_code=0, stdout="ok", stderr="")
        mock_session.exec.return_value = mock_res

        install_output = comp.install(mock_session)
        self.assertIn("comandos de instalação executados com sucesso", install_output)

        validate_output = comp.validate(mock_session)
        self.assertIn("comandos de validação executados com sucesso", validate_output)

    def test_registry_get_tailscale_supports_install_and_validate(self):
        comp_def = ComponentDefinition(name="tailscale")
        comp = ComponentRegistry.get(comp_def)
        
        mock_session = MagicMock()
        mock_res = MagicMock(exit_code=0, stdout="ok", stderr="")
        mock_session.exec.return_value = mock_res

        install_output = comp.install(mock_session)
        validate_output = comp.validate(mock_session)

        self.assertIn("instalação", install_output)
        self.assertIn("validação", validate_output)


if __name__ == "__main__":
    unittest.main()
