from enoslib.objects import Host
from enoslib.service.emul.netem import NetemInConstraint, NetemInOutSource, NetemOutConstraint
from enoslib.tests.unit import EnosTest


class TestAddConstraint(EnosTest):
    def test_different_if_are_added(self):
        nc1 = NetemInConstraint("eth0", "delay 10ms")
        nc2 = NetemInConstraint("eth1", "delay 10ms")
        h = Host("1.1.1.1")
        source = NetemInOutSource(h)
        source.add_constraints([nc1, nc2])
        self.assertCountEqual([nc1, nc2], source.constraints)

    def test_same_if_are_overwritten(self):
        nc1 = NetemInConstraint("eth0", "delay 10ms")
        nc2 = NetemInConstraint("eth0", "delay 20ms")
        h = Host("1.1.1.1")
        source = NetemInOutSource(h)
        source.add_constraints([nc1, nc2])
        self.assertCountEqual([nc2], source.constraints)

    def test_different_xgress_are_added(self):
        nc1 = NetemInConstraint("eth0", "delay 10ms")
        nc2 = NetemOutConstraint("eth0", "delay 10ms")
        h = Host("1.1.1.1")
        source = NetemInOutSource(h)
        source.add_constraints([nc1, nc2])
        self.assertCountEqual([nc1, nc2], source.constraints)

    def test_different_xgress_ifs_are_added(self):
        nc1 = NetemInConstraint("eth0", "delay 10ms")
        nc2 = NetemOutConstraint("eth0", "delay 10ms")
        nc3 = NetemInConstraint("eth1", "delay 10ms")
        nc4 = NetemOutConstraint("eth1", "delay 10ms")
        h = Host("1.1.1.1")
        source = NetemInOutSource(h)
        source.add_constraints([nc1, nc2, nc3, nc4])
        self.assertCountEqual([nc1, nc2, nc3, nc4], source.constraints)