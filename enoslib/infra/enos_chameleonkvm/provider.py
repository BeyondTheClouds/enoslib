from typing import Optional, Tuple

import enoslib.infra.enos_openstack.provider as openstack
from enoslib.objects import Networks, Roles


class Chameleonkvm(openstack.Openstack):
    def init(
        self, force_deploy: bool = False, start_time: Optional[int] = None, **kwargs
    ) -> Tuple[Roles, Networks]:
        return super().init(force_deploy)

    def destroy(self, wait: bool = False, **kwargs):
        super().destroy()

    def offset_walltime(self, offset: int):
        raise NotImplementedError(
            "Please Implement me to enjoy the power of multi platforms experiments."
        )
