import json
import logging

from app.cloud.dto import CloudMessage, CloudResponse, CloudError, CloudErrorDetail

logger = logging.getLogger(__name__)


def parse_message(raw: str) -> CloudMessage | None:
    """Deserializa uma mensagem JSON recebida da Cloud."""

    try:
        data = json.loads(raw)
        return CloudMessage.model_validate(data)
    except Exception as exc:
        logger.error("Failed to parse cloud message: %s", exc)
        return None


def build_response(
    request_id: str,
    message_type: str | None = None,
    payload: dict | None = None,
) -> str:
    """Serializa uma resposta para enviar à Cloud."""

    response = CloudResponse(
        request_id=request_id,
        origin="agent",
        success=True,
        type=message_type,
        payload=payload or {},
    )
    return response.model_dump_json(exclude_none=True)


def build_error(
    request_id: str,
    code: str,
    message: str,
) -> str:
    """Serializa uma mensagem de erro para enviar à Cloud."""

    error = CloudError(
        request_id=request_id,
        origin="agent",
        success=False,
        error=CloudErrorDetail(
            code=code,
            message=message,
        ),
    )
    return error.model_dump_json()

