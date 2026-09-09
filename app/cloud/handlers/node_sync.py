import logging
from collections import OrderedDict
from pydantic import ValidationError

from app.cloud.dispatcher import SendFunc
from app.cloud.dto import CloudMessage, NodeSyncEventDataDTO
from app.cloud.protocol import build_response, build_error
from app.database.session import SessionLocal
from app.services.environment_state_sync_service import EnvironmentStateSyncService

logger = logging.getLogger(__name__)

# Cache de tamanho limitado (LRU) para controle de idempotência por event_id
_MAX_PROCESSED_EVENTS = 1000
_processed_events: OrderedDict[str, bool] = OrderedDict()


def _is_duplicate_event(event_id: str | None) -> bool:
    """Verifica se o event_id já foi processado anteriormente."""
    if not event_id:
        return False

    if event_id in _processed_events:
        return True

    _processed_events[event_id] = True
    if len(_processed_events) > _MAX_PROCESSED_EVENTS:
        _processed_events.popitem(last=False)

    return False


class NodeSyncHandler:
    """Handler responsável por receber e processar eventos incrementais de nós da VPN (node.*).

    Valida segurança (environment_id), versão do contrato (version=1), idempotência (event_id)
    e delega para o `EnvironmentStateSyncService`.
    """

    @staticmethod
    async def handle_node_event(message: CloudMessage, send: SendFunc) -> None:
        event_id = message.get_event_id()
        request_id = message.request_id or event_id or "unknown"
        received_env_id = message.get_environment_id()

        logger.info(
            "[event_received] Event '%s' received (event_id=%s, env_id=%s)",
            message.type,
            event_id,
            received_env_id,
        )

        # 1. Checagem de Idempotência
        if event_id and _is_duplicate_event(event_id):
            logger.info("[event_ignored] Duplicate event_id '%s' received. Skipping processing.", event_id)
            if message.request_id:
                await send(build_response(request_id=message.request_id, payload={"status": "SKIPPED_DUPLICATE"}))
            return

        # 2. Validação da Versão do Contrato
        if message.version and message.version != 1:
            logger.warning("[event_rejected] Unsupported contract version: %s (event_id=%s)", message.version, event_id)
            if message.request_id:
                await send(build_error(request_id=message.request_id, code="UNSUPPORTED_VERSION", message="Version not supported"))
                 # 3. Processar deltas ou snapshot (suporta 'nodes', 'deltas' ou objeto único)
        raw_data = message.get_data_dict()
        nodes_list = None
        if isinstance(raw_data, dict):
            nodes_list = raw_data.get("nodes") or raw_data.get("deltas")

        items_to_process = []
        is_full_sync = message.type == "node.sync.response" or (isinstance(nodes_list, list) and message.type.endswith(".response"))

        if isinstance(nodes_list, list):
            items_to_process = [d for d in nodes_list if isinstance(d, dict)]
        elif isinstance(raw_data, dict):
            items_to_process = [raw_data]

        if not items_to_process and not is_full_sync:
            logger.warning("[event_rejected] No valid delta/node items found in event '%s'", message.type)
            if message.request_id:
                await send(build_error(request_id=message.request_id, code="EMPTY_PAYLOAD", message="No deltas to process"))
            return

        # 4. Execução no Serviço de Sincronização com Sessão Isolada
        try:
            with SessionLocal() as db:
                sync_service = EnvironmentStateSyncService(db)

                # 4a. Validação do Contexto de Ambiente
                if not sync_service.validate_context(received_env_id):
                    logger.warning(
                        "[event_rejected] Environment context mismatch for event '%s' (received_env_id=%s)",
                        message.type,
                        received_env_id,
                    )
                    if message.request_id:
                        await send(build_error(request_id=message.request_id, code="ENVIRONMENT_MISMATCH", message="Environment mismatch"))
                    return

                # 4b. Tratar resposta de Snapshot Completo (Full Sync + Prune)
                if is_full_sync:
                    print(f"\n==================================================")
                    print(f"[WS RECEBIDO] Snapshot Completo de Nós Recebido da Cloud! (Tipo: {message.type}, Total no Payload: {len(items_to_process)})")
                    print(f"==================================================")

                    dto_list = []
                    for item in items_to_process:
                        try:
                            dto_list.append(NodeSyncEventDataDTO.model_validate(item))
                        except ValidationError as val_err:
                            logger.error("[event_rejected] Invalid node item in full sync snapshot: %s", val_err)
                            continue

                    res = sync_service.reconcile_full_snapshot(dto_list)
                    print(f"[WS PROCESSADO] Snapshot Aplicado com Sucesso! {res['processed']} nós reconciliados, {res['pruned']} nós obsoletos expurgados.\n")
                    logger.info("[sync_full_applied] Full snapshot reconciled: processed=%d, pruned=%d", res["processed"], res["pruned"])
                else:
                    # Processar eventos incrementais de deltas
                    for item in items_to_process:
                        try:
                            data_dto = NodeSyncEventDataDTO.model_validate(item)
                        except ValidationError as val_err:
                            logger.error("[event_rejected] Invalid delta item in '%s': %s", message.type, val_err)
                            continue

                        action = (data_dto.action or "").upper()
                        if action in ("NODE_REMOVED", "NODE_DELETED") or message.type == "node.removed":
                            removed = sync_service.remove_node_state(data_dto)
                            print(f"[WS DELTA] Remoção de nó processada (node_id={data_dto.node_id}, removido={removed})")
                            logger.info("[node_removed] Node removal processed (node_id=%s, removed=%s)", data_dto.node_id, removed)
                        else:
                            updated_node = sync_service.upsert_node_state(data_dto)
                            if updated_node:
                                node_identifier = getattr(updated_node, "headscale_node_id", None) or getattr(updated_node, "machine_id", None) or getattr(updated_node, "cloud_connection_id", None)
                                node_kind = getattr(updated_node, "node_type", "client")
                                print(f"[WS DELTA] Nó atualizado (identificador={node_identifier}, tipo={node_kind}, online={updated_node.online})")
                                logger.info(
                                    "[sync_delta_applied] Node '%s' state updated successfully (node_id=%s, type=%s, online=%s)",
                                    message.type,
                                    node_identifier,
                                    node_kind,
                                    updated_node.online,
                                )

            # 5. Resposta de ACK para a Cloud (se request_id estiver presente)
            if message.request_id:
                response = build_response(
                    request_id=message.request_id,
                    payload={"status": "SUCCESS", "event_id": event_id},
                )
                await send(response)

            logger.info("[event_accepted] Event '%s' processed cleanly.", message.type)

        except Exception as exc:
            logger.error("[event_error] Failed to process event '%s': %s", message.type, exc, exc_info=True)
            if message.request_id:
                err_resp = build_error(
                    request_id=message.request_id,
                    code="INTERNAL_ERROR",
                    message="Internal error processing state delta",
                )
                await send(err_resp)
