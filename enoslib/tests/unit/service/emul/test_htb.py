from enoslib.objects import Host
from enoslib.service.emul.htb import HTBConstraint, HTBSource
from enoslib.tests.unit import EnosTest


class TestAddConstraint(EnosTest):
    def test_different_target_are_added(self):
        nc1 = HTBConstraint("eth0", "10ms", "1.1.1.2")
        nc2 = HTBConstraint("eth0", "10ms", "1.1.1.3")
        h = Host("1.1.1.1")
        source = HTBSource(h)
        source.add_constraints([nc1, nc2])
        self.assertCountEqual(source.constraints, [nc1, nc2])

    def test_existing_target_is_overwritten(self):
        nc1 = HTBConstraint("eth0", "10ms", "1.1.1.2")
        nc2 = HTBConstraint("eth0", "20ms", "1.1.1.2")
        h = Host("1.1.1.1")
        source = HTBSource(h)
        source.add_constraints([nc1, nc2])
        self.assertCountEqual(source.constraints, [nc2])

    def test_existing_target_is_overwritten_inc(self):
        nc1 = HTBConstraint("eth0", "10ms", "1.1.1.2")
        nc2 = HTBConstraint("eth0", "20ms", "1.1.1.2")
        h = Host("1.1.1.1")
        source = HTBSource(h)
        source.add_constraints([nc1])
        source.add_constraints([nc2])
        source.add_constraints([nc1, nc2])
        self.assertCountEqual(source.constraints, [nc2])


class TestGeneratedCommands(EnosTest):
    def test_ipv4(self):
        nc = HTBConstraint("eth0", "10ms", "1.1.1.2")
        self.assertCountEqual(
            ["tc qdisc del dev eth0 root || true"], nc.remove_commands()
        )

        # attach an htb queueing discipline
        self.assertCountEqual(
            ["tc qdisc add dev eth0 root handle 1: htb"], nc.add_commands()
        )

        # the tc/htb boilerplate
        self.assertCountEqual(
            [
                "tc class add dev eth0 parent 1: classid 1:2 htb rate 10gbit",
                "tc qdisc add dev eth0 parent 1:2 handle 11: netem delay 10ms",
                "tc filter add dev eth0 parent 1: protocol ip u32 match ip dst 1.1.1.2 flowid 1:2",  # noqa
            ],
            nc.commands(1),
        )

    def test_ipv4_with_loss(self):
        nc = HTBConstraint("eth0", "10ms", "1.1.1.2", loss="0.5%")
        self.assertCountEqual(
            ["tc qdisc del dev eth0 root || true"], nc.remove_commands()
        )

        # attach an htb queueing discipline
        self.assertCountEqual(
            ["tc qdisc add dev eth0 root handle 1: htb"], nc.add_commands()
        )

        # the tc/htb boilerplate
        self.assertCountEqual(
            [
                "tc class add dev eth0 parent 1: classid 1:2 htb rate 10gbit",
                "tc qdisc add dev eth0 parent 1:2 handle 11: netem delay 10ms loss 0.5%",  # noqa
                "tc filter add dev eth0 parent 1: protocol ip u32 match ip dst 1.1.1.2 flowid 1:2",  # noqa
            ],
            nc.commands(1),
        )

    def test_ipv6(self):
        nc = HTBConstraint("eth0", "10ms", "2001:660:4406:700:1::d")
        self.assertCountEqual(
            ["tc qdisc del dev eth0 root || true"], nc.remove_commands()
        )

        # attach an htb queueing discipline
        self.assertCountEqual(
            ["tc qdisc add dev eth0 root handle 1: htb"], nc.add_commands()
        )

        # the tc/htb boilerplate
        self.assertCountEqual(
            [
                "tc class add dev eth0 parent 1: classid 1:2 htb rate 10gbit",
                "tc qdisc add dev eth0 parent 1:2 handle 11: netem delay 10ms",
                "tc filter add dev eth0 parent 1: protocol ipv6 u32 match ip6 dst 2001:660:4406:700:1::d flowid 1:2",  # noqa
            ],
            nc.commands(1),
        )
