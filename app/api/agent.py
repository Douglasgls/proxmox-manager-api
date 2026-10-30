from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from app.schemas.agent_config import AgentConfigUpdate, AgentConfigResponse, AgentTestConnection
from app.services.agent_config_service import AgentConfigService
from app.core.dependencies import get_agent_config_service
from app.integrations.proxmox.proxmox_client import ProxmoxClient
from app.integrations.proxmox.exceptions import (
    ProxmoxAPIError,
    ProxmoxConnectionError,
    ProxmoxPermissionError,
)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/config", response_model=AgentConfigResponse)
def get_config(
    service: AgentConfigService = Depends(get_agent_config_service)
):
    """Retorna a configuração atual, mascarando o token do Proxmox."""
    return service.get_config()


@router.post("/config", response_model=AgentConfigResponse)
def save_config(
    data: AgentConfigUpdate,
    service: AgentConfigService = Depends(get_agent_config_service)
):
    """Valida a conexão com o Proxmox e, se sucesso, salva ou atualiza a configuração do Agent."""
    try:
        client = ProxmoxClient(
            host=data.proxmox_host,
            user=data.proxmox_user,
            token_name=data.proxmox_token_name,
            token_value=data.proxmox_token_value,
            node=data.proxmox_node,
        )
        # Validate connection before saving
        client.get_version()
    except ProxmoxPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permissão insuficiente no Proxmox VE: {e.message}",
        )
    except ProxmoxConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Falha na conexão com Proxmox. Configuração não salva: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno ao validar a conexão com Proxmox: {str(e)}"
        )
        
    return service.save_config(data)


@router.post("/test-connection")
def test_connection(data: AgentTestConnection):
    """
    Testa a conexão com o Proxmox utilizando as credenciais informadas,
    sem salvá-las no banco.
    """
    try:
        client = ProxmoxClient(
            host=data.proxmox_host,
            user=data.proxmox_user,
            token_name=data.proxmox_token_name,
            token_value=data.proxmox_token_value,
            node=data.proxmox_node,
        )
        # Tenta conectar e validar a versão
        client.get_version()
        
        # Validação adicional de leitura do nó (Sys.Audit)
        warning_msg = None
        try:
            client.get_node_status()
        except ProxmoxPermissionError as perm_err:
            warning_msg = (
                f"Conectado com sucesso, mas o token/usuário não possui a permissão '{perm_err.required_permission}' "
                f"no caminho '{perm_err.path}'. Adicione a permissão no Proxmox VE (Datacenter > Permissions) "
                f"para habilitar o monitoramento de recursos do host."
            )

        if warning_msg:
            return {
                "success": True,
                "message": warning_msg,
                "has_warning": True,
            }

        return {"success": True, "message": "Conexão com o Proxmox VE estabelecida e validada com sucesso."}
    except ProxmoxPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permissão insuficiente no Proxmox VE: {e.message}",
        )
    except ProxmoxConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Falha na conexão: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno ao testar conexão: {str(e)}"
        )


from app.security.dependencies import get_current_user
from app.models.user import User

@router.post("/restart")
def restart_agent(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Solicita o reinício do Agent.
    O processo recebe SIGTERM e o systemd realiza o restart.
    """

    def do_restart():
        import os
        import signal
        import time

        time.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)

    background_tasks.add_task(do_restart)

    return {"message": "Reiniciando o agente em instantes..."}

@router.get("/status")
def get_agent_status(
    service: AgentConfigService = Depends(get_agent_config_service)
):
    """
    Retorna o status geral de prontidão do Agent.
    """
    config = service.get_config()
    readiness = "READY" if config.configured else "NOT_CONFIGURED"
    
    return {
        "version": "1.0.0",
        "agent_status": "Em execução",
        "readiness": readiness,
    }
