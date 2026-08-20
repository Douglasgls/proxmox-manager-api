import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.cloud import crypto
from app.cloud.dto import AgentRegistrationDTO
from app.cloud.manager import cloud_manager
from app.cloud.models import AgentSettings
from app.cloud.repository import AgentSettingsRepository
from app.database.session import SessionLocal

from dotenv import load_dotenv

load_dotenv()

router = APIRouter()


@router.post(
    "/cloud/register",
    summary="Registrar Environment Token",
    description=(
        "Recebe o Environment Token informado pelo usuário, "
        "criptografa e salva na tabela agent_settings. "
        "A partir deste momento a conexão com a Cloud é iniciada automaticamente."
    ),
)
async def register_agent(data: AgentRegistrationDTO):
    if not os.getenv("CLOUD_URL"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLOUD_URL is not configured.",
        )

    encrypted_token = crypto.encrypt(data.environment_token)

    with SessionLocal() as db:
        repository = AgentSettingsRepository(db)
        settings = repository.get()

        if settings:
            settings.environment_token_encrypted = encrypted_token
            settings.registered_at = datetime.now(timezone.utc)
            settings.jwt = settings.jwt
            settings.jwt_expires_at = settings.jwt_expires_at
            repository.update(settings)
        else:
            settings = AgentSettings(
                environment_token_encrypted=encrypted_token,
                registered_at=datetime.now(timezone.utc),
            )
            repository.save(settings)

    # Notificar o connection manager que o token foi registrado
    await cloud_manager.connection_manager.notify_registration()

    return {
        "status": "registered",
        "message": "Agent registered. Cloud connection starting...",
    }


@router.get(
    "/cloud/status",
    summary="Status da conexão com a Cloud",
)
def cloud_status():
    with SessionLocal() as db:
        repository = AgentSettingsRepository(db)
        settings = repository.get()

        nodes_count = 0
        online_count = 0

        if settings:
            from app.tailscale.model import TailscaleNode
            from app.models.client_connection import ClientConnection
            t_nodes = db.query(TailscaleNode).all()
            c_conns = db.query(ClientConnection).all()
            nodes_count = len(t_nodes) + len(c_conns)
            online_count = sum(1 for n in t_nodes if n.online) + sum(1 for c in c_conns if c.online)

    if not settings or not settings.environment_token_encrypted:
        return {
            "registered": False,
            "connected": False,
            "message": "Agent not registered yet.",
            "cloud_url": os.getenv("CLOUD_URL"),
        }

    connected = cloud_manager.connection_manager._ws_client.is_connected

    jwt_valid = False
    if settings.jwt and settings.jwt_expires_at:
        now = datetime.now(timezone.utc)
        expires_at = settings.jwt_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        jwt_valid = expires_at > now

    return {
        "registered": True,
        "connected": connected,
        "jwt_valid": jwt_valid,
        "cloud_environment_id": settings.cloud_environment_id,
        "cloud_url": os.getenv("CLOUD_URL"),
        "registered_at": settings.registered_at.isoformat() if settings.registered_at else None,
        "jwt_expires_at": settings.jwt_expires_at.isoformat() if settings.jwt_expires_at else None,
        "last_ping": "2s" if connected else None,
        "total_nodes": nodes_count,
        "online_nodes": online_count,
    }


@router.get(
    "/cloud/details",
    summary="Detalhes completos da integração com a Cloud e nós da VPN",
    description="Retorna informações de registro, tokens, IDs remotos e o estado dos nós VPN sincronizados da Cloud.",
)
def cloud_details():
    with SessionLocal() as db:
        repository = AgentSettingsRepository(db)
        settings = repository.get()

        if not settings or not settings.environment_token_encrypted:
            return {
                "registered": False,
                "connected": False,
                "message": "Agent not registered yet.",
                "cloud_url": os.getenv("CLOUD_URL"),
                "nodes": [],
            }

        from app.tailscale.model import TailscaleNode
        from app.models.client_connection import ClientConnection

        t_nodes = db.query(TailscaleNode).all()
        c_conns = db.query(ClientConnection).all()
        nodes_list = []
        online_count = 0

        # Containers publicados
        for n in t_nodes:
            is_online = n.online
            if is_online:
                online_count += 1

            c_name = n.container.name if n.container else None
            nodes_list.append({
                "headscale_node_id": n.headscale_node_id,
                "machine_id": n.machine_id,
                "tailscale_ip": n.tailscale_ip,
                "online": is_online,
                "service_running": n.service_running,
                "node_type": "container",
                "hostname": n.hostname or c_name,
                "container_id": n.container_id,
                "proxmox_container_id": n.proxmox_container_id,
                "container_name": c_name,
                "last_sync": n.last_sync.isoformat() if n.last_sync else None,
            })

        # Clientes VPN externos conectados
        for c in c_conns:
            is_online = c.online
            if is_online:
                online_count += 1

            c_name = c.container.name if c.container else None
            nodes_list.append({
                "headscale_node_id": c.headscale_node_id,
                "cloud_connection_id": c.cloud_connection_id,
                "tailscale_ip": c.tailscale_ip,
                "online": is_online,
                "service_running": is_online,
                "node_type": "client",
                "hostname": c.hostname,
                "container_id": c.container_id,
                "proxmox_container_id": c.container.container_number if c.container else None,
                "container_name": c_name,
                "last_sync": c.updated_at.isoformat() if c.updated_at else None,
            })

    connected = cloud_manager.connection_manager._ws_client.is_connected

    jwt_valid = False
    if settings.jwt and settings.jwt_expires_at:
        now = datetime.now(timezone.utc)
        expires_at = settings.jwt_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        jwt_valid = expires_at > now

    return {
        "registered": True,
        "connected": connected,
        "jwt_valid": jwt_valid,
        "cloud_environment_id": settings.cloud_environment_id,
        "cloud_url": os.getenv("CLOUD_URL"),
        "registered_at": settings.registered_at.isoformat() if settings.registered_at else None,
        "jwt_expires_at": settings.jwt_expires_at.isoformat() if settings.jwt_expires_at else None,
        "total_nodes": len(nodes_list),
        "online_nodes": online_count,
        "nodes": nodes_list,
    }


@router.post(

    "/cloud/reconnect",
    summary="Reconectar com a Cloud",
)
async def reconnect_agent():
    with SessionLocal() as db:
        repository = AgentSettingsRepository(db)
        settings = repository.get()

    if not settings or not settings.environment_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent is not registered yet.",
        )

    await cloud_manager.connection_manager.notify_registration()

    return {
        "status": "reconnecting",
        "message": "Reconnection triggered.",
    }

