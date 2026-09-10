import os
import logging
from app.repositories.agent_config_repository import AgentConfigRepository
from app.models.agent_config import AgentConfig
from app.schemas.agent_config import AgentConfigUpdate, AgentConfigResponse
from app.security.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)


class AgentConfigService:

    def __init__(self, repository: AgentConfigRepository):
        self.repository = repository

    def get_config(self) -> AgentConfigResponse:
        config = self.repository.get_config()
        if not config:
            return AgentConfigResponse(configured=False)

        return AgentConfigResponse(
            configured=True,
            proxmox_host=config.proxmox_host,
            proxmox_user=config.proxmox_user,
            proxmox_token_name=config.proxmox_token_name,
            proxmox_node=config.proxmox_node,
            default_storage=config.default_storage,
            default_template=config.default_template,
        )

    def get_credentials(self) -> dict | None:
        """Retorna as credenciais completas (incluindo o token descriptografado) para uso interno."""
        config = self.repository.get_config()
        if not config:
            return None
            
        return {
            "host": config.proxmox_host,
            "user": config.proxmox_user,
            "token_name": config.proxmox_token_name,
            "token_value": decrypt(config.proxmox_token_value),
            "node": config.proxmox_node,
            "default_storage": config.default_storage,
            "default_template": config.default_template,
        }

    def save_config(self, data: AgentConfigUpdate) -> AgentConfigResponse:
        config = self.repository.get_config()
        encrypted_token = encrypt(data.proxmox_token_value)
        
        if config:
            config.proxmox_host = data.proxmox_host
            config.proxmox_user = data.proxmox_user
            config.proxmox_token_name = data.proxmox_token_name
            config.proxmox_token_value = encrypted_token
            config.proxmox_node = data.proxmox_node
            if data.default_storage is not None:
                config.default_storage = data.default_storage
            if data.default_template is not None:
                config.default_template = data.default_template
            
            self.repository.update(config)
        else:
            config = AgentConfig(
                proxmox_host=data.proxmox_host,
                proxmox_user=data.proxmox_user,
                proxmox_token_name=data.proxmox_token_name,
                proxmox_token_value=encrypted_token,
                proxmox_node=data.proxmox_node,
                default_storage=data.default_storage,
                default_template=data.default_template,
            )
            self.repository.create(config)
            
        return self.get_config()

    def bootstrap_from_env(self):
        """Lê do .env e migra para o banco, se ainda não houver configuração."""
        if self.repository.get_config() is not None:
            return

        host = os.getenv("PROXMOX_HOST")
        user = os.getenv("PROXMOX_USER")
        token_name = os.getenv("PROXMOX_TOKEN_NAME")
        token_value = os.getenv("PROXMOX_TOKEN_VALUE")
        node = os.getenv("PROXMOX_NODE")
        default_storage = os.getenv("PROXMOX_DEFAULT_STORAGE")
        default_template = os.getenv("PROXMOX_DEFAULT_TEMPLATE")

        if host and user and token_name and token_value and node:
            logger.info("Migrando configuração do Proxmox do .env para o banco de dados...")
            update_data = AgentConfigUpdate(
                proxmox_host=host,
                proxmox_user=user,
                proxmox_token_name=token_name,
                proxmox_token_value=token_value,
                proxmox_node=node,
                default_storage=default_storage,
                default_template=default_template,
            )
            self.save_config(update_data)
            logger.info("Migração de configuração concluída.")
