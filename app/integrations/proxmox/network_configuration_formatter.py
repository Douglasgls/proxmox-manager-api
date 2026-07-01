from app.models.network_configuration import (
    NetworkConfiguration,
    NetworkIpMode,
)


class ProxmoxNetworkConfigurationFormatter:

    def build_net0(
        self,
        network: NetworkConfiguration,
    ) -> str:

        return ",".join(
            self._build_net0_parts(
                network
            )
        )


    def _build_net0_parts(
        self,
        network: NetworkConfiguration,
    ) -> list[str]:

        parts = [
            f"name={network.interface_name}",
            f"bridge={network.bridge}",
            self._build_ip(network),
            self._build_firewall(network),
        ]

        parts.extend(
            self._build_optional_parts(
                network
            )
        )

        return parts


    def _build_ip(
        self,
        network: NetworkConfiguration,
    ) -> str:

        if network.ip_mode == NetworkIpMode.STATIC:
            return self._build_static(
                network
            )

        return self._build_dhcp()


    def _build_static(
        self,
        network: NetworkConfiguration,
    ) -> str:

        return f"ip={network.ip_address}/{network.cidr}"


    def _build_dhcp(
        self,
    ) -> str:

        return "ip=dhcp"


    def _build_firewall(
        self,
        network: NetworkConfiguration,
    ) -> str:

        return f"firewall={int(network.firewall)}"


    def _build_optional_parts(
        self,
        network: NetworkConfiguration,
    ) -> list[str]:

        parts: list[str] = []

        if network.gateway:
            parts.append(
                f"gw={network.gateway}"
            )

        if network.mtu:
            parts.append(
                f"mtu={network.mtu}"
            )

        if network.vlan:
            parts.append(
                f"tag={network.vlan}"
            )

        if network.mac_address:
            parts.append(
                f"hwaddr={network.mac_address}"
            )

        return parts
