import re
from ipaddress import ip_address as parse_ip_address
from app.core.exceptions import DomainValidationError
from app.models.container import Container
from app.models.network_configuration import (
    NetworkConfiguration,
    NetworkIpMode,
)


class ContainerNetworkService:
    """Serviço responsável por validação, construção e aplicação de configurações de rede para containers LXC."""

    def build_network(
        self,
        bridge: str,
        ip_mode: str,
        ip_address: str | None = None,
        cidr: int | None = None,
        gateway: str | None = None,
        firewall: bool = False,
        mtu: int | None = None,
        vlan: int | None = None,
        mac_address: str | None = None,
    ) -> NetworkConfiguration:
        network = NetworkConfiguration(
            bridge=bridge,
            ip_mode=self.parse_network_ip_mode(ip_mode),
            ip_address=ip_address,
            cidr=cidr,
            gateway=gateway,
            firewall=bool(firewall),
            mtu=mtu,
            vlan=vlan,
            mac_address=mac_address,
        )

        self.validate_network(network)
        return network

    def build_network_from_container(
        self,
        container: Container,
        network_data: dict,
    ) -> NetworkConfiguration:
        values = self.current_network_values(container)

        if (
            network_data.get("ip_mode") == NetworkIpMode.DHCP.value
            and not self.has_static_fields(network_data)
        ):
            values.update(self.empty_static_values())

        values.update(network_data)
        return self.build_network(**values)

    def current_network_values(self, container: Container) -> dict:
        ip_mode = container.ip_mode or NetworkIpMode.DHCP.value

        return {
            "bridge": container.bridge or "vmbr0",
            "ip_mode": ip_mode,
            "ip_address": self.current_static_value(ip_mode, container.ip_address),
            "cidr": self.current_static_value(ip_mode, container.cidr),
            "gateway": self.current_static_value(ip_mode, container.gateway),
            "firewall": container.firewall,
            "mtu": container.mtu,
            "vlan": container.vlan,
            "mac_address": container.mac_address,
        }

    def current_static_value(self, ip_mode: str, value):
        if ip_mode == NetworkIpMode.DHCP.value:
            return None
        return value

    def empty_static_values(self) -> dict:
        return {
            "ip_address": None,
            "cidr": None,
            "gateway": None,
        }

    def has_static_fields(self, network_data: dict) -> bool:
        return any(
            network_data.get(field) is not None
            for field in ("ip_address", "cidr", "gateway")
        )

    def parse_network_ip_mode(self, ip_mode: str) -> NetworkIpMode:
        try:
            return NetworkIpMode(ip_mode)
        except ValueError as exc:
            raise DomainValidationError(
                "Modo de IP inválido. Use 'dhcp' ou 'static'."
            ) from exc

    def validate_network(self, network: NetworkConfiguration):
        if not network.bridge:
            raise DomainValidationError("Bridge de rede é obrigatória")

        validators = {
            NetworkIpMode.DHCP: self._validate_dhcp,
            NetworkIpMode.STATIC: self._validate_static,
        }
        validators[network.ip_mode](network)
        self._validate_optional_network_fields(network)

    def _validate_dhcp(self, network: NetworkConfiguration):
        if (
            network.ip_address
            or network.gateway
            or network.cidr is not None
        ):
            raise DomainValidationError(
                "Configuração DHCP não permite ip_address, gateway ou cidr"
            )

    def _validate_static(self, network: NetworkConfiguration):
        missing = [
            field
            for field, value in {
                "ip_address": network.ip_address,
                "gateway": network.gateway,
                "cidr": network.cidr,
            }.items()
            if value is None
        ]

        if missing:
            raise DomainValidationError(
                "Configuração static exige: " + ", ".join(missing)
            )

        self._validate_ip_address("ip_address", network.ip_address)
        self._validate_ip_address("gateway", network.gateway)
        self._validate_cidr(network.cidr)

    def _validate_optional_network_fields(self, network: NetworkConfiguration):
        if network.mtu is not None and network.mtu <= 0:
            raise DomainValidationError("MTU deve ser maior que zero")

        if network.vlan is not None and not 1 <= network.vlan <= 4094:
            raise DomainValidationError("VLAN deve estar entre 1 e 4094")

        self._validate_mac_address(network.mac_address)

    def _validate_ip_address(self, field_name: str, value: str | None):
        try:
            parse_ip_address(value)
        except ValueError as exc:
            raise DomainValidationError(f"{field_name} inválido") from exc

    def _validate_cidr(self, cidr: int | None):
        if cidr is None:
            return
        if not 0 <= cidr <= 32:
            raise DomainValidationError("CIDR deve estar entre 0 e 32")

    def _validate_mac_address(self, mac_address: str | None):
        if mac_address is None:
            return
        if not re.fullmatch(r"[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}", mac_address):
            raise DomainValidationError("MAC address inválido")

    def apply_network_configuration(
        self,
        container: Container,
        network: NetworkConfiguration,
    ):
        container.bridge = network.bridge
        container.ip_mode = network.ip_mode.value
        container.ip_address = network.ip_address
        container.cidr = network.cidr
        container.gateway = network.gateway
        container.firewall = network.firewall
        container.mtu = network.mtu
        container.vlan = network.vlan
        container.mac_address = network.mac_address
