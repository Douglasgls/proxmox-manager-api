import logging
from pydantic import ValidationError

from app.cloud.dto import CloudMessage, ContainerProvisionPayloadDTO
from app.cloud.dispatcher import SendFunc
from app.cloud.protocol import build_response, build_error
from app.cloud.container_provision_service import ContainerProvisionService
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)


class ContainerProvisionHandler:
    """Handler responsável por tratar eventos de provisionamento de container (container.provision).

    Handler fino: apenas valida DTO, delega para o ContainerProvisionService
    e envia o envelope de resposta via WebSocket (ACK ou Error).
    """

    @staticmethod
    async def handle_provision(message: CloudMessage, send: SendFunc) -> None:
        request_id = message.request_id
        logger.info("[%s] Recebido evento container.provision da Cloud", request_id)

        # 1. Validar DTO da mensagem
        try:
            # Se o request_id no payload estiver ausente, injeta o request_id da mensagem
            payload_data = dict(message.payload)
            if "request_id" not in payload_data or not payload_data["request_id"]:
                payload_data["request_id"] = request_id

            dto = ContainerProvisionPayloadDTO.model_validate(payload_data)
            print(f"\n[PROVISION HANDLER] Payload validado com sucesso para o container {dto.container_id} (request_id={request_id})\n")
        except ValidationError as val_err:
            logger.error("[%s] Payload inválido para container.provision: %s", request_id, val_err)
            print(f"\n[PROVISION HANDLER ERRO] Payload inválido: {val_err}\n")
            err_response = build_error(
                request_id=request_id,
                code="INVALID_PAYLOAD",
                message=f"Payload inválido para provisionamento: {val_err}",
            )
            await send(err_response)
            return

        # 2. Delegar para o serviço de orquestração com sessão de banco isolada
        try:
            with SessionLocal() as db:
                service = ContainerProvisionService(db)
                await service.provision_container(dto)


            # 3. Responder confirmação (ACK) de sucesso para a Cloud
            success_response = build_response(
                request_id=request_id,
                payload={
                    "status": "SUCCESS",
                    "container_id": dto.container_id,
                },
            )
            await send(success_response)
            logger.info("[%s] Resposta de sucesso do provisionamento enviada à Cloud", request_id)

        except Exception as exc:
            logger.error("[%s] Falha no provisionamento do container %s: %s", request_id, dto.container_id, exc)
            err_response = build_error(
                request_id=request_id,
                code="PROVISIONING_FAILED",
                message=str(exc),
            )
            await send(err_response)
