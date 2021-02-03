from ipaddress import ip_interface, ip_network
from enoslib.errors import *
from enoslib.objects import Host, IPAddress, DefaultNetwork, _ansible_map_network_device
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
    def test__map_devices_all_match_single(self):
        networks = [
            DefaultNetwork(roles=["a"], network=ip_network("1.2.3.0/24")),
            DefaultNetwork(roles=["b"], network=ip_network("4.5.6.0/24")),
        ]
        # from ansible
        devices = [
            {
                "device": "eth0",
                "ipv4": [{"address": "1.2.3.5", "netmask": "255.255.255.0"}],
            },
            {
                "device": "eth1",
                "ipv4": [{"address": "4.5.6.7", "netmask": "255.255.255.0"}],
            },
        ]
        expected = [
            {"cidr": "4.5.6.7/24", "device": "eth1"},
            {"cidr": "1.2.3.4/24", "device": "eth0"},
        ]
        expected = [
            (networks[0], IPAddress("1.2.3.5/24", roles=["a"], device="eth0")),
            (networks[1], IPAddress("4.5.6.7/24", roles=["b"], device="eth1")),
        ]
        self.assertCountEqual(expected, _ansible_map_network_device(networks, devices))

    def test__map_devices_all_match_multiple(self):
        devices = [
            {
                "device": "eth0",
                "ipv4": [{"address": "1.2.3.5", "netmask": "255.255.255.0"}],
            },
            {
                "device": "eth1",
                "ipv4": [{"address": "1.2.3.254", "netmask": "255.255.255.0"}],
            },
        ]
        networks = [
            DefaultNetwork(roles=["a"], network=ip_network("1.2.3.0/24")),
            DefaultNetwork(roles=["b"], network=ip_network("4.5.6.0/24")),
        ]
        # only the last match is taken into account
        expected = [
            (networks[0], IPAddress("1.2.3.5/24", roles=["a"], device="eth0")),
            (networks[0], IPAddress("1.2.3.254/24", roles=["a"], device="eth1")),
        ]
        self.assertCountEqual(expected, _ansible_map_network_device(networks, devices))


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
