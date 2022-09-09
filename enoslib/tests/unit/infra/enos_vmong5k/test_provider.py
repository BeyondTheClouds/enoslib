from unittest import mock

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
    @mock.patch(
        "enoslib.infra.enos_vmong5k.configuration.get_cluster_site",
        return_value="site1",
    )
    def test_do_build_g5k_conf(
        self,
        mock_get_cluster_site_vmong5k,
        mock_get_cluster_site_g5k,
        mock_find_node_number,
    ):
        conf = Configuration()
        conf.add_machine(roles=["r1"], cluster="cluster1", number=10, flavour="tiny")
        conf.finalize()
        g5k_conf = _do_build_g5k_conf(conf)
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
        mac = "00:00:00:00:00:01"
        machine = MachineConfiguration(
            roles=["r1"], flavour="tiny", undercloud=[host], number=1, macs=[mac]
        )
        machines = [machine]

        vmong5k_roles = _distribute(machines)
        self.assertEqual(1, len(vmong5k_roles["r1"]))
        vm = vmong5k_roles["r1"][0]
        self.assertEqual(mac, vm.eui)
        self.assertEqual(host, vm.pm)

    def test_distribute_2_vms_1_host(self):
        host = Host("paravance-1")
        macs = [
            "00:00:00:00:00:01",
            "00:00:00:00:00:02",
        ]
        machine = MachineConfiguration(
            roles=["r1"], flavour="tiny", undercloud=[host], number=2, macs=macs
        )
        machines = [machine]

        vmong5k_roles = _distribute(machines)
        self.assertEqual(2, len(vmong5k_roles["r1"]))

        actual_macs = [str(vm.eui) for vm in vmong5k_roles["r1"]]
        # check macs
        self.assertCountEqual(macs, actual_macs)
        vm = vmong5k_roles["r1"][0]
        # we skip the first mac
        self.assertEqual(host, vm.pm)

        vm = vmong5k_roles["r1"][1]
        self.assertEqual(host, vm.pm)

    def test_distribute_2_vms_2_hosts(self):
        host0 = Host("paravance-1")
        host1 = Host("paravance-2")
        macs = [
            "00:00:00:00:00:01",
            "00:00:00:00:00:02",
        ]
        machine = MachineConfiguration(
            roles=["r1"], flavour="tiny", undercloud=[host0, host1], number=2, macs=macs
        )
        machines = [machine]

        vmong5k_roles = _distribute(machines, macs)
        self.assertEqual(2, len(vmong5k_roles["r1"]))

        actual_macs = [str(vm.eui) for vm in vmong5k_roles["r1"]]

        # check macs
        self.assertCountEqual(macs, actual_macs)

        # check hosts
        vm = vmong5k_roles["r1"][0]
        # we skip the first mac
        self.assertEqual(host0, vm.pm)

        vm = vmong5k_roles["r1"][1]
        self.assertEqual(host1, vm.pm)
