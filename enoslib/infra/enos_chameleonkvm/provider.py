# -*- coding: utf-8 -*-

import enoslib.infra.enos_openstack.provider as openstack


class Chameleonkvm(openstack.Openstack):
    def init(self, force_deploy=False, **kwargs):
        return super(Chameleonkvm, self).init(force_deploy)

    def destroy(self):
        super(Chameleonkvm, self).destroy()

    def offset_walltime(self, offset: int):
        raise NotImplementedError(
            "Please Implement me to enjoy the power of multi plaforms experiments."
        )
