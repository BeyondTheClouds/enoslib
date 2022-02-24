from enoslib.objects import Host, NetDevice, IPAddress, DefaultNetwork
from enoslib.local import LocalHost
from enoslib.docker import DockerHost

from . import EnosTest


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

    def test_get_set_extra(self):
        extra = {"original_key": "original_value"}
        h = TestEqHosts._make_host(extra)
        self.assertDictEqual(extra, h.get_extra())

        h.set_extra(original_key="new_value")
        self.assertDictEqual({"original_key": "new_value"}, h.get_extra())

        h.reset_extra()
        self.assertDictEqual(extra, h.get_extra())

        self.assertDictEqual(
            {"original_key": "new_value"},
            h.set_extra(original_key="new_value").get_extra())

        self.assertDictEqual(
            extra,
            h.reset_extra().get_extra()
        )

    def test_dont_remove_special_host(self):
        localhost = LocalHost()
        extra = dict(ansible_connection="local")
        self.assertDictEqual(extra, localhost.get_extra())
        self.assertDictEqual(extra, localhost.reset_extra().get_extra())

        docker = DockerHost("test", "container", Host("1.2.3.4"))
        extra = dict(ansible_connection="docker",
                     ansible_docker_extra_args="-H ssh://1.2.3.4",
                     mitogen_via="1.2.3.4")
        self.assertDictEqual(extra, docker.get_extra())
        self.assertDictEqual(extra, docker.reset_extra().get_extra())



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
