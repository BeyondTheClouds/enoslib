from enoslib.objects import (
    BridgeDevice,
    Host,
    IPAddress,
    DefaultNetwork,
    NetDevice,
    _build_devices,
)
from enoslib.enos_inventory import EnosInventory
from enoslib.tests.unit import EnosTest


def _find_host_line(ini, role):
    ini = ini.split("\n")
    idx = ini.index("[r1]")
    return ini[idx + 1]


class TestGenerateInventoryString(EnosTest):
    def test_address(self):
        h = Host("1.2.3.4")
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual(
            "1.2.3.4 ansible_host='1.2.3.4' ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'",  # noqa
            line,
        )

    def test_address_alias(self):
        h = Host("1.2.3.4", alias="alias")
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual(
            "alias ansible_host='1.2.3.4' ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'",  # noqa
            line,
        )

    def test_address_user(self):
        h = Host("1.2.3.4", user="foo")
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual(
            "1.2.3.4 ansible_host='1.2.3.4' ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null' ansible_ssh_user='foo'",  # noqa
            line,
        )

    def test_port(self):
        h = Host("1.2.3.4", port=2222)
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual(
            "1.2.3.4 ansible_host='1.2.3.4' ansible_port='2222' ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'",  # noqa
            line,
        )

    def test_address_gateway(self):
        h = Host("1.2.3.4", extra={"gateway": "4.3.2.1"})
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual(
            "1.2.3.4 ansible_host='1.2.3.4' ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand=\"ssh -W %h:%p -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null 4.3.2.1\"'",  # noqa
            line,
        )

    def test_address_gateway_same_user(self):
        h = Host("1.2.3.4", user="foo", extra={"gateway": "4.3.2.1"})
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual(
            "1.2.3.4 ansible_host='1.2.3.4' ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand=\"ssh -W %h:%p -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -l foo 4.3.2.1\"' ansible_ssh_user='foo'",  # noqa
            line,
        )


class TestGetHostNet(EnosTest):
    def test_map_devices_with_secondary_ipv4(self):
        n1, n2 = [
            DefaultNetwork(address="1.2.3.0/24"),
            DefaultNetwork(address="4.5.6.0/24"),
        ]
        networks = dict(role1=[n1, n2])
        # from ansible
        facts = {
            "ansible_interfaces": ["eth0", "eth1"],
            "ansible_eth0": {
                "device": "eth0",
                "ipv4": {"address": "1.2.3.4", "netmask": "255.255.255.0"},
                "ipv4_secondaries": [
                    {"address": "4.5.6.7", "netmask": "255.255.255.0"}
                ],
                "type": "ether",
            },
        }
        expected = [
            NetDevice(
                "eth0", {IPAddress("1.2.3.4/24", n1), IPAddress("4.5.6.7/24", n2)}
            ),
        ]

        self.assertCountEqual(expected, _build_devices(facts, networks))

    def test__map_devices_all_match_single(self):
        n1, n2 = [
            DefaultNetwork(address="1.2.3.0/24"),
            DefaultNetwork(address="4.5.6.0/24"),
        ]
        networks = dict(role1=[n1, n2])
        # from ansible
        facts = {
            "ansible_interfaces": ["eth0", "eth1"],
            "ansible_eth0": {
                "device": "eth0",
                "ipv4": [{"address": "1.2.3.4", "netmask": "255.255.255.0"}],
                "type": "ether",
            },
            "ansible_eth1": {
                "device": "eth1",
                "ipv4": [{"address": "4.5.6.7", "netmask": "255.255.255.0"}],
                "type": "ether",
            },
        }
        expected = [
            NetDevice("eth0", {IPAddress("1.2.3.4/24", n1)}),
            NetDevice("eth1", {IPAddress("4.5.6.7/24", n2)}),
        ]

        self.assertCountEqual(expected, _build_devices(facts, networks))

    def test__map_devices_all_match_multiple(self):
        n1 = DefaultNetwork(address="1.2.3.0/24")
        n2 = DefaultNetwork(address="4.5.6.0/24")
        networks = dict(role1=[n1, n2])
        facts = {
            "ansible_interfaces": ["eth0", "eth1"],
            "ansible_eth0": {
                "device": "eth0",
                "ipv4": [{"address": "1.2.3.4", "netmask": "255.255.255.0"}],
                "type": "ether",
            },
            "ansible_eth1": {
                "device": "eth1",
                "ipv4": [{"address": "1.2.3.254", "netmask": "255.255.255.0"}],
                "type": "ether",
            },
        }
        expected = [
            NetDevice("eth0", {IPAddress("1.2.3.4/24", n1)}),
            NetDevice("eth1", {IPAddress("1.2.3.254/24", n1)}),
        ]

        self.assertCountEqual(expected, _build_devices(facts, networks))

    def test__map_devices_same_device(self):
        n1, n2 = [
            DefaultNetwork(address="1.2.3.0/24"),
            DefaultNetwork(address="4.5.6.0/24"),
        ]
        networks = dict(role1=[n1, n2])
        facts = {
            "ansible_interfaces": ["eth0", "eth1"],
            "ansible_eth0": {
                "device": "eth0",
                "ipv4": [
                    {"address": "1.2.3.4", "netmask": "255.255.255.0"},
                    {"address": "1.2.3.5", "netmask": "255.255.255.0"},
                ],
                "type": "ether",
            },
        }
        expected = [
            NetDevice(
                "eth0",
                {IPAddress("1.2.3.5/24", n1), IPAddress("1.2.3.4/24", n1)},
            ),
        ]

        self.assertCountEqual(expected, _build_devices(facts, networks))

    def test_map_devices_bridge(self):
        n1, n2 = [
            DefaultNetwork(address="1.2.3.0/24"),
            DefaultNetwork(address="4.5.6.0/24"),
        ]
        networks = dict(role1=[n1, n2])
        facts = {
            "ansible_interfaces": ["eth0", "eth1"],
            "ansible_eth0": {
                "device": "br0",
                "ipv4": [
                    {"address": "1.2.3.4", "netmask": "255.255.255.0"},
                    {"address": "1.2.3.5", "netmask": "255.255.255.0"},
                ],
                "type": "bridge",
                "interfaces": ["eth0", "eth1"],
            },
        }
        expected = [
            BridgeDevice(
                "br0",
                {
                    IPAddress("1.2.3.5/24", n1),
                    IPAddress("1.2.3.4/24", n1),
                },
                ["eth0", "eth1"],
            ),
        ]

        self.assertCountEqual(expected, _build_devices(facts, networks))

    # todo bridge
