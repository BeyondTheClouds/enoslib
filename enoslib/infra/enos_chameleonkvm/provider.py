import enoslib.infra.enos_openstack.provider as openstack


class Chameleonkvm(openstack.Openstack):
    def init(self, force_deploy=False, **kwargs):
        return super().init(force_deploy)

    def destroy(self, wait=False):
        super().destroy()

    def offset_walltime(self, offset: int):
        raise NotImplementedError(
            "Please Implement me to enjoy the power of multi platforms experiments."
        )
