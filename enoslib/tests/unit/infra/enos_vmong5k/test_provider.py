from enoslib.infra.enos_g5k.objects import G5kEnosSubnetNetwork, G5kSubnetNetwork
import mock

from enoslib.objects import Host
from enoslib.infra.enos_vmong5k.configuration import Configuration, MachineConfiguration
from enoslib.infra.enos_vmong5k.provider import (
    _do_build_g5k_conf,
    _distribute,
)
from enoslib.tests.unit import EnosTest


class TestBuildG5kConf(EnosTest):
    @mock.patch(
        "enoslib.infra.enos_vmong5k.provider._find_nodes_number", return_value=2
    )
    @mock.patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="site1"
    )
    def test_do_build_g5k_conf(self, mock_get_cluster_site, mock_find_node_number):
        conf = Configuration()
        conf.add_machine(roles=["r1"], cluster="cluster1", number=10, flavour="tiny")
        conf.finalize()
        g5k_conf = _do_build_g5k_conf(conf, "rennes")
        # it's valid
        g5k_conf.finalize()

        # machines
        self.assertEqual(1, len(g5k_conf.machines))
        machine = g5k_conf.machines[0]
        self.assertEqual("cluster1", machine.cluster)
        self.assertEqual(2, machine.nodes)
        # role have been expanded with the unique cookie
        self.assertEqual(2, len(machine.roles))

        # networks
        self.assertEqual(2, len(g5k_conf.networks))
        self.assertTrue(g5k_conf.networks[0].type in ["prod", "slash_22"])
        self.assertTrue(g5k_conf.networks[1].type in ["prod", "slash_22"])


class TestDistribute(EnosTest):
    def test_distribute_minimal(self):

        host = Host("paravance-1")
        machine = MachineConfiguration(
            roles=["r1"], flavour="tiny", undercloud=[host], number=1
        )
        machines = [machine]

        g5k_subnet = G5kEnosSubnetNetwork(
            "10.140.40.0/22", "172.16.11.254", "172.16.11.25"
        )

        vmong5k_roles = _distribute(machines, [g5k_subnet])
        self.assertEqual(1, len(vmong5k_roles["r1"]))
        vm = vmong5k_roles["r1"][0]
        # we skip the first mac
        it_mac = g5k_subnet.free_macs
        next(it_mac)
        self.assertEqual(next(it_mac), vm.eui)
        self.assertEqual(host, vm.pm)

    def test_distribute_minimal_skip(self):

        host = Host("paravance-1")
        machine = MachineConfiguration(
            roles=["r1"], flavour="tiny", undercloud=[host], number=1
        )
        machines = [machine]

        g5k_subnet = G5kEnosSubnetNetwork(
            "10.140.40.0/22", "172.16.11.254", "172.16.11.25"
        )

        vmong5k_roles = _distribute(machines, [g5k_subnet], skip=10)
        self.assertEqual(1, len(vmong5k_roles["r1"]))
        vm = vmong5k_roles["r1"][0]
        # we skip the first mac + 10 more
        it_mac = g5k_subnet.free_macs
        for i in range(11):
            next(it_mac)
        self.assertEqual(next(it_mac), vm.eui)
        self.assertEqual(host, vm.pm)

    def test_distribute_2_vms_1_host(self):
        host = Host("paravance-1")
        machine = MachineConfiguration(
            roles=["r1"], flavour="tiny", undercloud=[host], number=2
        )
        machines = [machine]

        g5k_subnet = G5kEnosSubnetNetwork(
            "10.140.40.0/22", "172.16.11.254", "172.16.11.25"
        )

        vmong5k_roles = _distribute(machines, [g5k_subnet])
        self.assertEqual(2, len(vmong5k_roles["r1"]))
        vm = vmong5k_roles["r1"][0]
        # we skip the first mac
        it_mac = g5k_subnet.free_macs
        next(it_mac)
        self.assertEqual(next(it_mac), vm.eui)
        self.assertEqual(host, vm.pm)

        vm = vmong5k_roles["r1"][1]
        self.assertEqual(next(it_mac), vm.eui)
        self.assertEqual(host, vm.pm)

    def test_distribute_2_vms_2_hosts(self):
        host0 = Host("paravance-1")
        host1 = Host("paravance-2")
        machine = MachineConfiguration(
            roles=["r1"], flavour="tiny", undercloud=[host0, host1], number=2
        )
        machines = [machine]

        g5k_subnet = G5kEnosSubnetNetwork(
            "10.140.40.0/22", "172.16.11.254", "172.16.11.25"
        )

        vmong5k_roles = _distribute(machines, [g5k_subnet])
        self.assertEqual(2, len(vmong5k_roles["r1"]))
        vm = vmong5k_roles["r1"][0]
        # we skip the first mac
        it_mac = g5k_subnet.free_macs
        next(it_mac)
        self.assertEqual(next(it_mac), vm.eui)
        self.assertEqual(host0, vm.pm)

        vm = vmong5k_roles["r1"][1]
        self.assertEqual(next(it_mac), vm.eui)
        self.assertEqual(host1, vm.pm)
