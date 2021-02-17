from ipaddress import ip_interface, ip_network
from enoslib.errors import *
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
            "1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'",
            line,
        )

    def test_address_alias(self):
        h = Host("1.2.3.4", alias="alias")
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual(
            "alias ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'",
            line,
        )

    def test_address_user(self):
        h = Host("1.2.3.4", user="foo")
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual(
            "1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null' ansible_ssh_user='foo'",
            line,
        )

    def test_port(self):
        h = Host("1.2.3.4", port=2222)
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual(
            "1.2.3.4 ansible_host=1.2.3.4 ansible_port='2222' ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'",
            line,
        )

    def test_address_gateway(self):
        h = Host("1.2.3.4", extra={"gateway": "4.3.2.1"})
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual(
            "1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand=\"ssh -W %h:%p -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null 4.3.2.1\"'",
            line,
        )

    def test_address_gateway_same_user(self):
        h = Host("1.2.3.4", user="foo", extra={"gateway": "4.3.2.1"})
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual(
            "1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand=\"ssh -W %h:%p -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -l foo 4.3.2.1\"' ansible_ssh_user='foo'",
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
                "eth0", set([IPAddress("1.2.3.4/24", n1), IPAddress("4.5.6.7/24", n2)])
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
            NetDevice("eth0", set([IPAddress("1.2.3.4/24", n1)])),
            NetDevice("eth1", set([IPAddress("4.5.6.7/24", n2)])),
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
            NetDevice("eth0", set([IPAddress("1.2.3.4/24", n1)])),
            NetDevice("eth1", set([IPAddress("1.2.3.254/24", n1)])),
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
                set([IPAddress("1.2.3.5/24", n1), IPAddress("1.2.3.4/24", n1)]),
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
                set(
                    [
                        IPAddress("1.2.3.5/24", n1),
                        IPAddress("1.2.3.4/24", n1),
                    ]
                ),
                ["eth0", "eth1"],
            ),
        ]

        self.assertCountEqual(expected, _build_devices(facts, networks))

    # todo bridge


class TestEqHosts(EnosTest):
    @staticmethod
    def _make_host(extra={}):
        return Host(
            address="1.2.3.4",
            alias="foo",
            user="foo",
            keyfile="file://foo.id_rsa",
            port=22,
            extra=extra,
        )

    def test__hash(self):
        self.assertEqual(
            Host("1.2.3.4").__hash__(),
            Host("1.2.3.4").__hash__(),
            "Hosts have the same hash because we can "
            "SSH on each of them in the same manner",
        )

        self.assertNotEqual(
            Host("1.2.3.4").__hash__(),
            Host("1.2.3.5").__hash__(),
            "Hosts should not have the same hash because we "
            "cannot SSH on each of them in the same manner",
        )

        h1 = TestEqHosts._make_host()
        h2 = TestEqHosts._make_host(extra={"extra_ip": "5.6.7.8"})
        self.assertEqual(
            h1.__hash__(),
            h2.__hash__(),
            "Hosts have the same hash because we can "
            "SSH on each of them in the same manner "
            "(we do not look at `extra` for SSH)",
        )

        h1 = TestEqHosts._make_host()
        h2 = TestEqHosts._make_host()
        h2.net_devices = set([NetDevice(name="eth0")])
        self.assertEqual(
            h1.__hash__(),
            h2.__hash__(),
            "Hosts have the same hash because we can "
            "SSH on each of them in the same manner "
            "(we do not look at `extra_devices` for SSH)",
        )

    def test__extra(self):
        extra1 = {"extra_ip": "5.6.7.8"}
        extra2 = {"extra_ip": "5.6.7.8"}

        h1 = TestEqHosts._make_host(extra1)
        h2 = TestEqHosts._make_host(extra1)
        self.assertEqual(h1, h2)

        h1 = TestEqHosts._make_host(extra1)
        h2 = TestEqHosts._make_host(extra2)
        self.assertEqual(
            h1, h2, "Hosts with an extra object with the same values are equivalent"
        )

        h1 = TestEqHosts._make_host(extra1)
        extra1.update(extra_ip="1.2.3.4")
        h2 = TestEqHosts._make_host(extra1)
        self.assertNotEqual(h1, h2, "Extra is not shared across Hosts")


class TestFilterAddresses(EnosTest):
    def test_filter_addresses(self):
        h1 = Host("1.2.3.4")
        self.assertCountEqual(
            [], h1.filter_addresses(), "No device attached means" "No address to get"
        )

        h1 = Host("1.2.3.4")
        h1.net_devices = set([NetDevice(name="eth0", addresses=set())])
        self.assertCountEqual(
            [],
            h1.filter_addresses(),
            "One device attached but no address" "No address to get",
        )

        h1 = Host("1.2.3.4")
        address = IPAddress("1.2.3.4", None)
        h1.net_devices = set([NetDevice(name="eth0", addresses=set([address]))])
        self.assertCountEqual(
            [],
            h1.filter_addresses(),
            "One device attached with one address but no network attached"
            "No address to get",
        )
        self.assertCountEqual(
            [address],
            h1.filter_addresses(include_unknown=True),
            "One device attached with one address but no network attached"
            "One address to get if include_unknown=True",
        )

        h1 = Host("1.2.3.4")
        address = IPAddress("1.2.3.4", DefaultNetwork(address="1.2.3.0/24"))
        h1.net_devices = set([NetDevice(name="eth0", addresses=set([address]))])
        self.assertCountEqual(
            [address],
            h1.filter_addresses(),
            "One device attached with one address and a known network"
            "One address to get",
        )

        h1 = Host("1.2.3.4")
        network = DefaultNetwork(address="1.2.3.0/24")
        address = IPAddress("1.2.3.4", network)
        h1.net_devices = set([NetDevice(name="eth0", addresses=set([address]))])
        self.assertCountEqual(
            [address],
            h1.filter_addresses([network]),
            "One device attached with one address and a known network"
            "One address to get (not filtered out)",
        )

        h1 = Host("1.2.3.4")
        network = DefaultNetwork(address="1.2.3.0/24")
        network2 = DefaultNetwork(address="1.2.4.0/24")
        address = IPAddress("1.2.3.4", network)
        h1.net_devices = set([NetDevice(name="eth0", addresses=set([address]))])
        self.assertCountEqual(
            [],
            h1.filter_addresses([network2]),
            "One device attached with one address and a known network"
            "No address to get (filtered out)",
        )

        h1 = Host("1.2.3.4")
        network = DefaultNetwork(address="1.2.3.0/24")
        network2 = DefaultNetwork(address="1.2.4.0/24")
        address = IPAddress("1.2.3.4", network)
        address2 = IPAddress("1.2.4.4", network2)
        h1.net_devices = set(
            [NetDevice(name="eth0", addresses=set([address, address2]))]
        )
        self.assertCountEqual(
            [address],
            h1.filter_addresses([network]),
            "One device attached with two addresses on two known network"
            "One address to get (one filtered out)",
        )
