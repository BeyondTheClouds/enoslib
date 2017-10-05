# -*- coding: utf-8 -*-

import enoslib.infra.enos_openstack.provider as openstack


class Chameleonkvm(openstack.Openstack):

    def init(self, force_deploy=False):
        return super(Chameleonkvm, self).init(force_deploy)

    def destroy(self):
        super(Chameleonkvm, self).destroy()

    def default_config(self):
        default_config = super(Chameleonkvm, self).default_config()
        default_config.update({
            'type': 'chameleonkvm',
            'image': 'CC-Ubuntu16.04',
            'user': 'cc',
            'dns_nameservers': ['129.114.97.1',
                                '129.114.97.2',
                                '129.116.84.203'],
        })

        return default_config
