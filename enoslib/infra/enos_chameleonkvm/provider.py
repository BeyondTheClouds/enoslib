# -*- coding: utf-8 -*-

import enoslib.infra.enos_openstack.provider as openstack


class Chameleonkvm(openstack.Openstack):
    def init(self, force_deploy=False):
        return super(Chameleonkvm, self).init(force_deploy)

    def destroy(self):
        super(Chameleonkvm, self).destroy()

    def test_slot(self, start_time: int) -> bool:
        """Test if it is possible to reserve the configuration corresponding
        to this provider at start_time"""
        # Unimplemented
        return False
