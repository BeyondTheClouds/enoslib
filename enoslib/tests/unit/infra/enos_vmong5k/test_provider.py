from unittest import mock

from enoslib.infra.enos_vmong5k.configuration import Configuration, MachineConfiguration
from enoslib.infra.enos_vmong5k.provider import (
    _distribute,
    _do_build_g5k_conf,
    _find_nodes_number,
)
from enoslib.objects import Host
from enoslib.tests.unit import EnosTest
from enoslib.tests.unit.infra.enos_g5k.test_provider import get_offline_client


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


class TestNodesNumber(EnosTest):
    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_cores_allocation(self, mock_api):
        mock_api.return_value = get_offline_client()

        # Single small VM should require a single physical node
        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 1, "mem": 512},
            cluster="paravance",
            number=1,
        )
        self.assertEqual(1, _find_nodes_number(machine))

        # paravance has 16 cores, 32 threads
        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 2, "mem": 512},
            cluster="paravance",
            vcore_type="thread",
            number=16,
        )
        self.assertEqual(1, _find_nodes_number(machine))

        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 2, "mem": 512},
            cluster="paravance",
            vcore_type="core",
            number=16,
        )
        self.assertEqual(2, _find_nodes_number(machine))

        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 2, "mem": 512},
            cluster="paravance",
            vcore_type="thread",
            number=17,
        )
        self.assertEqual(2, _find_nodes_number(machine))

        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 2, "mem": 512},
            cluster="paravance",
            vcore_type="core",
            number=17,
        )
        self.assertEqual(3, _find_nodes_number(machine))

        # sagittaire has 2 cores, 2 threads
        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 1, "mem": 512},
            cluster="sagittaire",
            vcore_type="thread",
            number=2,
        )
        self.assertEqual(1, _find_nodes_number(machine))

        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 1, "mem": 512},
            cluster="sagittaire",
            vcore_type="core",
            number=2,
        )
        self.assertEqual(1, _find_nodes_number(machine))

        # A really big VM should still take one physical node
        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 64, "mem": 4096},
            cluster="paravance",
            number=1,
        )
        self.assertEqual(1, _find_nodes_number(machine))

    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_memory_allocation(self, mock_api):
        mock_api.return_value = get_offline_client()

        # 31 * 4 GiB should fit, but 32 * 4 GiB will not because of
        # reserved system memory.
        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 1, "mem": 4096},
            cluster="paravance",
            number=31,
        )
        self.assertEqual(1, _find_nodes_number(machine))

        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 1, "mem": 4096},
            cluster="paravance",
            number=32,
        )
        self.assertEqual(2, _find_nodes_number(machine))

        # neowise has 512 GiB of memory, 63 * 8 GiB should fit.
        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 1, "mem": 8192},
            cluster="neowise",
            number=63,
        )
        self.assertEqual(1, _find_nodes_number(machine))

        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 1, "mem": 8192},
            cluster="neowise",
            number=64,
        )
        self.assertEqual(2, _find_nodes_number(machine))

        # sagittaire only has 2 GiB of memory
        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 1, "mem": 512},
            cluster="sagittaire",
            number=2,
        )
        self.assertEqual(1, _find_nodes_number(machine))

        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 1, "mem": 1024},
            cluster="sagittaire",
            number=2,
        )
        self.assertEqual(2, _find_nodes_number(machine))

        # A really big VM should still take one physical node
        machine = MachineConfiguration(
            roles=["r1"],
            flavour_desc={"core": 1, "mem": 768 * 1024},
            cluster="neowise",
            number=1,
        )
        self.assertEqual(1, _find_nodes_number(machine))


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

        vmong5k_roles = _distribute(machines, None)
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

    def test_distribute_determinism(self):
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

        vmong5k_roles = _distribute(machines, None)
        mapping1 = []
        for h in vmong5k_roles["r1"]:
            mapping1.append((h.alias, h.pm))

        # changing the order in the undercloud
        machine = MachineConfiguration(
            roles=["r1"], flavour="tiny", undercloud=[host1, host0], number=2, macs=macs
        )
        machines = [machine]

        vmong5k_roles = _distribute(machines, None)
        mapping2 = []
        for h in vmong5k_roles["r1"]:
            mapping2.append((h.alias, h.pm))

        # the vm to pm mapping should remain the same regardless
        # the order in the undercloud
        self.assertCountEqual(mapping1, mapping2)
