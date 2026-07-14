from fastapi import APIRouter, Depends

from app.core.dependencies import (
    get_container_monitoring_service,
    get_host_monitoring_service,
    get_network_monitoring_service,
    get_storage_monitoring_service,
)
from app.dto.response.monitoring import (
    ContainerInventoryDTO,
    ContainerInventorySummaryDTO,
    ContainerMetricsDTO,
    HostInventoryDTO,
    HostMetricsDTO,
    NetworkInventoryDTO,
    StorageInventoryDTO,
)
from app.services.monitoring.container_monitoring_service import ContainerMonitoringService
from app.services.monitoring.host_monitoring_service import HostMonitoringService
from app.services.monitoring.network_monitoring_service import NetworkMonitoringService
from app.services.monitoring.storage_monitoring_service import StorageMonitoringService
from app.security.dependencies import get_current_user


router = APIRouter(
    prefix="/monitor",
    dependencies=[Depends(get_current_user)],
)


@router.get("/host/inventory", response_model=HostInventoryDTO)
def get_host_inventory(service: HostMonitoringService = Depends(get_host_monitoring_service)):
    return service.get_inventory()


@router.get("/host/metrics", response_model=HostMetricsDTO)
def get_host_metrics(service: HostMonitoringService = Depends(get_host_monitoring_service)):
    return service.get_metrics()


@router.get("/storage/inventory", response_model=list[StorageInventoryDTO])
def get_storage_inventory(service: StorageMonitoringService = Depends(get_storage_monitoring_service)):
    return service.get_inventory()


@router.get("/network/inventory", response_model=NetworkInventoryDTO)
def get_network_inventory(service: NetworkMonitoringService = Depends(get_network_monitoring_service)):
    return service.get_inventory()


@router.get("/containers/inventory", response_model=ContainerInventorySummaryDTO)
def get_containers_inventory(service: ContainerMonitoringService = Depends(get_container_monitoring_service)):
    return service.get_inventory()


@router.get("/containers/metrics", response_model=list[ContainerMetricsDTO])
def get_containers_metrics(service: ContainerMonitoringService = Depends(get_container_monitoring_service)):
    return service.get_metrics()


@router.get("/containers/{container_id}/inventory", response_model=ContainerInventoryDTO)
def get_container_inventory(
    container_id: int,
    service: ContainerMonitoringService = Depends(get_container_monitoring_service),
):
    return service.get_container_inventory(container_id)


@router.get("/containers/{container_id}/metrics", response_model=ContainerMetricsDTO)
def get_container_metrics(
    container_id: int,
    service: ContainerMonitoringService = Depends(get_container_monitoring_service),
):
    return service.get_container_metrics(container_id)
