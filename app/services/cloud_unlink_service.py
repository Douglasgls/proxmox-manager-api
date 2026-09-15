import logging
import os
from typing import Dict, Any

import httpx

from app.cloud.manager import cloud_manager
from app.cloud.repository import AgentSettingsRepository
from app.models.client_connection import ClientConnection
from app.models.container import Container
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)


class CloudUnlinkService:
    @staticmethod
    async def unlink(force: bool = False) -> Dict[str, Any]:
        """
        Orquestra o desvínculo do Agent com a Cloud.
        1. Bloqueia reconexões e encerra o WebSocket.
        2. Tenta fazer unregister na Cloud (se não for force=True).
        3. Limpa os vínculos no banco de dados local.
        """
        # 1. Bloqueia sync e reconexões
        logger.info("Encerrando conexão WebSocket e prevenindo reconexões...")
        await cloud_manager.connection_manager.stop()

        cloud_url = os.getenv("CLOUD_URL")
        cloud_success = False
        cloud_message = ""

        with SessionLocal() as db:
            repository = AgentSettingsRepository(db)
            settings = repository.get()
            jwt = settings.jwt if settings else None

        if not settings or not settings.environment_token_encrypted:
            return {
                "status": "already_unlinked",
                "message": "O Agent não está registrado em nenhuma Cloud.",
                "cloud_cleanup": True
            }

        # 2. Chama a Cloud para unregister
        if cloud_url and jwt:
            try:
                base_url = cloud_url.rstrip("/")
                unregister_url = f"{base_url}/api/agent/unregister"
                logger.info(f"Solicitando unregister à Cloud: {unregister_url}")
                
                async with httpx.AsyncClient() as client:
                    response = await client.delete(
                        unregister_url,
                        headers={"Authorization": f"Bearer {jwt}"},
                        timeout=10.0
                    )
                
                if response.status_code in (200, 204):
                    cloud_success = True
                    cloud_message = "Cloud cleanup confirmado."
                elif response.status_code == 401:
                    logger.warning("Token expirado na tentativa de unregister. Ignorando erro na Cloud se force=True.")
                    cloud_message = "Token expirado na Cloud."
                else:
                    logger.error(f"Erro na Cloud ao fazer unregister: {response.status_code} - {response.text}")
                    cloud_message = f"Erro na Cloud: {response.status_code}"
            except Exception as e:
                logger.error(f"Falha de rede ao contatar a Cloud para unregister: {e}")
                cloud_message = "Cloud indisponível ou erro de rede."
        else:
            cloud_message = "Sem token JWT ou URL da Cloud para notificar unregister."
        
        # 3. Tratamento de Resposta e force=True
        if not cloud_success and not force:
            return {
                "status": "error",
                "message": f"Falha ao remover ambiente na Cloud ({cloud_message}). Use force=true se deseja forçar a limpeza local.",
                "cloud_cleanup": False
            }

        # 4. Limpeza Local
        logger.info("Iniciando limpeza local de vínculos com a Cloud...")
        with SessionLocal() as db:
            # 4.1 Limpa as configurações de agent (volta a NOT_REGISTERED)
            repository = AgentSettingsRepository(db)
            current_settings = repository.get()
            if current_settings:
                current_settings.environment_token_encrypted = None
                current_settings.cloud_environment_id = None
                current_settings.jwt = None
                current_settings.jwt_expires_at = None
                current_settings.registered_at = None
                repository.update(current_settings)

            # 4.2 Desvincula containers da cloud (Mantém o container!)
            db.query(Container).filter(Container.cloud_container_id.is_not(None)).update(
                {"cloud_container_id": None}, synchronize_session=False
            )

            # 4.3 Desvincula client connections (Mantém a conexão localmente se útil)
            db.query(ClientConnection).filter(ClientConnection.cloud_connection_id.is_not(None)).update(
                {"cloud_connection_id": None}, synchronize_session=False
            )

            db.commit()

        logger.info("Agent desvinculado com sucesso localmente.")

        final_msg = "Agent desvinculado com sucesso."
        if force and not cloud_success:
            final_msg = f"Desvinculado localmente, mas a limpeza remota não pôde ser confirmada ({cloud_message}). O ambiente ainda pode existir no painel da Cloud."

        return {
            "status": "success",
            "message": final_msg,
            "cloud_cleanup": cloud_success
        }
