from ..configuration import BaseConfiguration
from .constants import (DEFAULT_ENV_NAME, DEFAULT_JOB_NAME, DEFAULT_JOB_TYPE,
                        DEFAULT_NUMBER, DEFAULT_QUEUE, DEFAULT_WALLTIME)
from .schema import SCHEMA


class Configuration(BaseConfiguration):

    _SCHEMA = SCHEMA

    def __init__(self):
        super().__init__()
        self.dhcp = True
        self.force_deploy = False
        self.env_name = DEFAULT_ENV_NAME
        self.job_name = DEFAULT_JOB_NAME
        self.job_type = DEFAULT_JOB_TYPE
        self.key = None
        self.oargrid_jobids = None
        self.queue = DEFAULT_QUEUE
        self.reservation = None
        self.walltime = DEFAULT_WALLTIME

        self._machine_cls = MachineConfiguration
        self._network_cls = NetworkConfiguration

    @classmethod
    def from_dictionnary(cls, dictionnary, validate=True):
        if validate:
            cls.validate(dictionnary)

        self = cls()

        for k in self.__dict__.keys():
            v = dictionnary.get(k)
            if v is not None:
                setattr(self, k, v)

        _resources = dictionnary["resources"]
        _machines = _resources["machines"]
        _networks = _resources["networks"]
        self.networks = [NetworkConfiguration.from_dictionnary(n) for n in
                         _networks]
        self.machines = [MachineConfiguration.from_dictionnary(
            m, self.networks) for m in _machines]

        self.finalize()
        return self

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if v is None or k in ["machines", "networks", "_machine_cls",
                                  "_network_cls"]:
                continue
            d.update({k: v})

        d.update(resources={
            "machines": [m.to_dict() for m in self.machines],
            "networks": [n.to_dict() for n in self.networks]
        })
        return d


class MachineConfiguration:

    def __init__(self, *,
                 roles=None,
                 cluster=None,
                 primary_network=None,
                 nodes=DEFAULT_NUMBER,
                 secondary_networks=None):
        # NOTE(msimonin): mandatory keys will be captured by the finalize
        # function of the configuration.
        self.roles = roles
        self.cluster = cluster
        self.primary_network = primary_network
        self.nodes = nodes
        self.secondary_networks = []
        if secondary_networks is not None:
            self.secondary_networks = secondary_networks

    @classmethod
    def from_dictionnary(cls, dictionnary, networks=None):
        if networks is None or networks == []:
            raise ValueError("At least one network must be set")

        roles = dictionnary["roles"]
        cluster = dictionnary["cluster"]
        primary_network_id = dictionnary["primary_network"]

        secondary_networks_ids = dictionnary.get("secondary_networks", [])

        primary_network = [n for n in networks if n.id == primary_network_id]
        if len(primary_network) < 1:
            raise ValueError("Primary network with id={id} not found".format(
                id=primary_network_id))

        secondary_networks = [n for n in networks if n.id in
                              secondary_networks_ids]
        if len(secondary_networks_ids) != len(secondary_networks):
            raise ValueError("Secondary network resolution fails")

        kwargs = {}
        nodes = dictionnary.get("nodes")
        if nodes is not None:
            kwargs.update(nodes=nodes)

        return cls(roles=roles,
                   cluster=cluster,
                   primary_network=primary_network[0],
                   secondary_networks=secondary_networks,
                   **kwargs)

    def to_dict(self):
        d = {}
        d.update(
            roles=self.roles,
            cluster=self.cluster,
            nodes=self.nodes,
            primary_network=self.primary_network.id,
            secondary_networks=[n.id for n in self.secondary_networks]
        )
        return d


class NetworkConfiguration:

    def __init__(self, *,
                 id=None,
                 roles=None,
                 type=None,
                 site=None):
        # NOTE(msimonin): mandatory keys will be captured by the finalize
        # function of the configuration.
        self.roles = roles
        self.id = id
        self.roles = roles
        self.type = type
        self.site = site

    @classmethod
    def from_dictionnary(cls, dictionnary):
        id = dictionnary["id"]
        type = dictionnary["type"]
        roles = dictionnary["roles"]
        site = dictionnary["site"]

        return cls(id=id, roles=roles, type=type, site=site)

    def to_dict(self):
        d = {}
        d.update(id=self.id,
                 type=self.type,
                 roles=self.roles,
                 site=self.site)
        return d
