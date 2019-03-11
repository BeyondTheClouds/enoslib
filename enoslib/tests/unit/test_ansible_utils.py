from enoslib.errors import *
from enoslib.host import Host
from enoslib.api import _update_hosts, _map_device_on_host_networks
from enoslib.enos_inventory import EnosInventory
from enoslib.utils import gen_rsc
from enoslib.tests.unit import EnosTest


def _find_host_line(ini, role):
    ini = ini.split("\n")
    idx =  ini.index("[r1]")
    return ini[idx + 1]


class TestGenerateInventoryString(EnosTest):

    def test_address(self):
        h = Host("1.2.3.4")
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'", line)

    def test_address_alias(self):
        h = Host("1.2.3.4", alias="alias")
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual("alias ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'", line)


    def test_address_user(self):
        h = Host("1.2.3.4", user="foo")
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null' ansible_ssh_user='foo'", line)


    def test_port(self):
        h = Host("1.2.3.4", port=2222)
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_port='2222' ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'", line)

    def test_address_gateway(self):
        h = Host("1.2.3.4", extra={'gateway': '4.3.2.1'})
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand=\"ssh -W %h:%p -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null 4.3.2.1\"'", line)

    def test_address_gateway_same_user(self):
        h = Host("1.2.3.4", user="foo", extra={'gateway': '4.3.2.1'})
        enos_inventory = EnosInventory(roles={"r1": [h]})
        ini = enos_inventory.to_ini_string()
        line = _find_host_line(ini, "r1")
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand=\"ssh -W %h:%p -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -l foo 4.3.2.1\"' ansible_ssh_user='foo'", line)



class TestGetHostNet(EnosTest):
    def test__map_devices_all_match_single(self):
        networks = [{
            "cidr": "1.2.3.4/24"
        }, {
            "cidr": "4.5.6.7/24"
        }]
        devices = [{
            "device": "eth0",
            "ipv4": [{"address": "1.2.3.5"}]
        }, {
            "device": "eth1",
            "ipv4": [{"address": "4.5.6.7"}]
        }]
        expected = [{
            "cidr": "4.5.6.7/24",
            "device": "eth1"
        }, {
            "cidr": "1.2.3.4/24",
            "device": "eth0"
        }]
        self.assertCountEqual(expected, _map_device_on_host_networks(networks, devices))

    def test__map_devices_all_match_multiple(self):
        networks = [{
            "cidr": "1.2.3.4/24"
        }, {
            "cidr": "4.5.6.7/24"
        }]
        devices = [{
            "device": "eth0",
            "ipv4": [{"address": "1.2.3.5"}]
        }, {
            "device": "eth1",
            "ipv4": [{"address": "1.2.3.254"}]
        }]
        # only the last match is taken into account
        expected = [{
            "cidr": "1.2.3.4/24",
            "device": "eth1"
        }, {
            "cidr": "4.5.6.7/24",
            "device": None
        }]
        self.assertCountEqual(expected, _map_device_on_host_networks(networks, devices))

    def test__map_devices_net_veth(self):
        networks = [{
            "cidr": "1.2.3.4/24"
        }, {
            "cidr": "4.5.6.7/24"
        }]
        devices = [{
            "device": "eth0",
            "ipv4": [{"address": "1.2.3.5"}]
        }, {
            "device": "veth0",
            "ipv4": []
        }]
        expected = [{
            "cidr": "4.5.6.7/24",
            "device": None
        }, {
            "cidr": "1.2.3.4/24",
            "device": "eth0"
        }]
        self.assertCountEqual(expected, _map_device_on_host_networks(networks, devices))


class TestUpdateHosts(EnosTest):

    def test__update_hosts(self):
        rsc = {"control": [Host("1.2.3.4", alias="foo"), Host("1.2.3.5", alias="bar")]}
        facts = {
            "foo": {
                "ansible_eth0": {
                    "ipv4": {"address": "1.2.3.1"}
                },
                "ansible_eth1": {
                    "ipv4": {"address": "2.2.3.1"}
                },
                "networks": [{
                    "cidr": "1.2.3.0/24",
                    "device": "eth0",
                    "roles": ["network1"]

                    }, {
                        "cidr": "2.2.3.0/24",
                        "device": "eth1",
                        "roles": ["network2"]
                    }]},
            "bar": {
                "ansible_eth0": {
                    "ipv4": {"address": "1.2.3.1"}
                },
                "ansible_eth1": {
                    "ipv4": {"address": "2.2.3.1"}
                },
                "networks": [{
                    "cidr": "1.2.3.0/24",
                    "device": "eth0",
                    "roles": ["network1"]
                }, {
                    "cidr": "2.2.3.0/24",
                    "device": "eth1",
                    "roles": ["network2"]
                }]},
        }

        _update_hosts(rsc, facts)
        for host in gen_rsc(rsc):
            self.assertEqual("eth0", host.extra["network1"])
            self.assertEqual("eth0", host.extra["network1_dev"])
            self.assertEqual("eth1", host.extra["network2"])
            self.assertEqual("eth1", host.extra["network2_dev"])

    def test__update_hosts_inverted(self):
        rsc = {"control": [Host("1.2.3.4", alias="foo"), Host("1.2.3.5", alias="bar")]}
        facts = {
            "foo": {
                # since 2.2.1 we need extra facts to be present
                "ansible_eth0": {
                    "ipv4": {"address": "1.2.3.1"}
                },
                "ansible_eth1": {
                    "ipv4": {"address": "2.2.3.1"}
                },
                "networks": [{
                    "cidr": "1.2.3.0/24",
                    "device": "eth0",
                    "roles": ["network1"]
                }, {
                    "cidr": "2.2.3.0/24",
                    "device": "eth1",
                    "roles": ["network2"]
                }]},
            "bar": {
                # since 2.2.1 we need extra facts to be present
                "ansible_eth0": {
                    "ipv4": {"address": "2.2.3.2"}
                },
                "ansible_eth1": {
                    "ipv4": {"address": "1.2.3.2"}
                },
                "networks": [{
                    "cidr": "1.2.3.0/24",
                    "device": "eth1",
                    "roles": ["network1"]
                }, {
                    "cidr": "2.2.3.0/24",
                    "device": "eth0",
                    "roles": ["network2"]
                }]},
            }

        _update_hosts(rsc, facts)
        for host in gen_rsc(rsc):
            if host.alias == "foo":
                self.assertEqual("eth0", host.extra["network1"])
                self.assertEqual("eth0", host.extra["network1_dev"])
                self.assertEqual("1.2.3.1", host.extra["network1_ip"])
                self.assertEqual("eth1", host.extra["network2"])
                self.assertEqual("eth1", host.extra["network2_dev"])
                self.assertEqual("2.2.3.1", host.extra["network2_ip"])
            elif host.alias == "bar":
                self.assertEqual("eth1", host.extra["network1"])
                self.assertEqual("eth1", host.extra["network1_dev"])
                self.assertEqual("1.2.3.2", host.extra["network1_ip"])
                self.assertEqual("eth0", host.extra["network2"])
                self.assertEqual("eth0", host.extra["network2_dev"])
                self.assertEqual("2.2.3.2", host.extra["network2_ip"])

    def test__update_hosts_unmatch(self):
        rsc = {"control": [Host("1.2.3.4", alias="foo")]}
        facts = {
            "foo": {
                "ansible_eth0": {
                    "ipv4": {"address": "1.2.3.1"}
                },
                "ansible_eth1": {
                    "ipv4": {"address": "2.2.3.2"}
                },
                "networks": [{
                    "cidr": "1.2.3.0/24",
                    "device": "eth0",
                    "roles": ["network1"]
                }, {
                    "cidr": "2.2.3.0/24",
                    "device": None
                }]},
        }

        _update_hosts(rsc, facts)
        for host in gen_rsc(rsc):
            self.assertEqual("eth0", host.extra["network1"])
            self.assertEqual("eth0", host.extra["network1_dev"])
            self.assertEqual("1.2.3.1", host.extra["network1_ip"])
            self.assertTrue("network2" not in host.extra)
            self.assertTrue("network2_dev" not in host.extra)
            self.assertTrue("network2_ip" not in host.extra)

