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
