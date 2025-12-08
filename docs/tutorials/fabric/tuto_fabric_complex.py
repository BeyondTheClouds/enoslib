import logging

import enoslib as en

try:
    import ruamel.yaml as yaml  # noqa: F401
except ImportError:
    import yaml  # noqa: F401

en.init_logging(level=logging.INFO)
en.check()


provider_conf = """
# ---------------------------------------------------------------------
# To provision GPUs, storage you would need to first request privileges
# on FABRIC. You can do that by creating a ticket on the FABRIC portal.
# ---------------------------------------------------------------------
name_prefix: complex-example
rc_file: secrets/fabric_rc
walltime: "02:00:00"
resources:
  machines:
    - roles:
      - personal
      site: UCSD
      image: default_rocky_8
      flavour: big
      number: 1
      gpus:
        - model: TeslaT4
      storage:
        - kind: NVME
          model: P4510
          mount_point: /mnt/nvme
        - kind: Storage
          model: NAS
          name: kiso-fabric-integration
          auto_mount: true
  networks:
    - roles:
        - v4
      kind: FABNetv4
      site: UCSD
      nic:
        kind: SharedNIC
        model: ConnectX-6
"""

# claim the resources
conf = en.FabricConf.from_dictionary(yaml.safe_load(provider_conf))
provider = en.Fabric(conf)
roles, networks = provider.init()
print(roles)
print(networks)

# destroy the boxes
provider.destroy()
