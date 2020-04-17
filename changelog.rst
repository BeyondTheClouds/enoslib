Changelog
===========

5.1.2
-----

- Task: automatic ``env_name`` change to remove colons from the name

5.1.1
-----

- Netem: Better support for large deployment (introduce `chunk_size` parameter)

5.1.0
-----

- Tasks:
    - review the internal of the implementation
    - support for nested tasks added
- Doc:
    - Add autodoc summary in the APIs pages (provided by autodocsumm)
    - Align some examples with the new Netem implementation

5.0.0
-----

- Upgrade Ansible to 2.9 (python 3.8 now supported)
- Service/conda: new service to control remote conda environments.
  Introduce `conda_run_command` (resp. `conda_play_on`) that
  wraps `api.run_command` (resp. `api.play_on`) and launch commands
  (resp. modules) in the context of an conda environment.
- Service/dask: deploy a Dask cluster (use the Conda service)
- VMonG5K:
    - allow to attach an extra disk to the virtual machines
    - improve documentation.
- Service/SimpleNetem: A simplified version of the Netem Service
  that sets homogeneous constraints on hosts.
- Service/Netem:
    - Fix an issue when the interface names contains a dash.
    - Fix: `symetric: False` wasn't taken into account
    - Speed up the rules deployment (everything is pre-generated on python side)
    - (BREAKING): Netem Schema
        - `groups` or `except` keys are now mandatory in the decription
        - `enable` key has been removed.
- Api: Add `when` in the top-level kwargs of `play_on` modules.
- Service/dstat: use a named session.

4.11.0
------

- Service/docker:
    - Allow to mount the whole docker dir elsewhere
      (e.g in /tmp/docker instead of /var/lib/docker)
    - Default to registry:None, meaning that this will
      deploy independent docker daemons

4.10.1
------

- Service/dstat: doc
- service/monitoring: typecheck


4.10.0
------

- Service/dstat: add a new dstat monitoring
- Doc: some fixes (comply with the discover_networks)

4.9.4
-----

- Doc: some fixes

4.9.3
-----

- Doc: some fixes / add a ref

4.9.2
-----

- Doc: add some refs in they-use-it.rst

4.9.1
-----

- Fix: include the missing BREAKING change of 4.9.0

4.9.0
------

- Doc: Add a ref
- Service/locust: Fix density option
- Service/Netem: support for bridged networks
- Api/BREAKING: `discover_networks` doesn't have side effects anymore on the hosts.

4.8.12
------

- Doc: Simplify network emulation example

4.8.11
------

- VMonG5K: Don't fail if #pms > #vms
- Doc: add madeus-openstack-benchmarks
- Service/locust: review, add a density option that controls
  the number of slave to start on each node.
- Doc: Expose the Locust documentation

4.8.10
------

- Service/monitoring: allow for some customisations
- VMonG5K: use the libvirt directory for all the operations

4.8.9
-----

- Service/netem: fix validate when network is partitioned

4.8.8
-----

- Doc: Add content for quick access
- Doc: Add parameters sweeper tutorial

4.8.7
-----

- Doc: clean and use continuation line
- Service/docker: remove useless statement

4.8.6
-----

- Api/play_on: don't gather facts twice
- VMonG5k: 🐎 enable virtio for network device 🐎
- Service/monitoring: add the influxdb datasource automatically

4.8.5
-----

- Api: Introduce ``ensure_python[2,3]`` to make sure python[2,3]
  is there and make it the default version (optionally)
- Api: ``wait_ssh`` now uses the raw module
- Api: rename some prior with a double underscore (e.g. ``__python3__``)

4.8.4
-----

- Doc: Handling of G5k custom images
- Host: Implementation of the __hash__() function
- API: ``play_on`` offers new strategies to gather Ansible facts
- type: Type definitions for Host, Role and Network

4.8.3
-----

- G5K/api: job_reload_from_name fix for anonymous user
- Doc: some cleaning, advertise mattermost channel

4.8.2
-----

- VMonG5K: some cleaning
- Host: copy the passed extra dict
- Skydive: fix docstring

4.8.1
-----

- Service/Monitoring: fix collector_address for telegraf agents

4.8.0
-----

- Enforce python3.6+ everywhere
- Add more functionnal tests
- Api: ``play_on`` accepts a ``priors`` parameters
- Add ``run`` command for simplicity sake
- ``enoslib.host.Host`` is now a dataclass
- Typecheck enabled in CI

4.7.0
-----

- G5k: Default to Debian10
- Vagrant: Defaut to Debian10
- VMonG5k:
    - Default to Debian10
    - Activate VLC console (fix an issue with newest G5K virt images...)
    - Run VMs as root

4.6.0
-----

- Chameleon: minor fixes, support for the primer example
- Vagrant: customized name and config is now supported
- Locust/service: initial version (locust.io)
- G5k: support for arbitrary SSH key

4.5.0
-----

- Dependencies: upgrade python-grid5000 to 0.1.0+
- VMonG5K/API break: use g5k api username instead of USER environment variable
- VMonG5K: make the provider idempotent

4.4.5
-----

- Doc: some fixes
- VMonG5k: change gateway description

4.4.4
-----

- Doc: distem makes use of stretch image by default

4.4.3
-----

- Doc: Doc updates (readme and distem)

4.4.2
-----

- Doc: update distem tutorial

4.4.1
-----

- Catch up changelog

4.4.0
-----

- New provider: Distem

4.3.1
-----

- G5k: fix walltime > 24h

4.3.0
-----

- G5k: ``get_api_username`` to retrieve the current user login
- Doc: fix ``play_on``

4.2.5
-----

- Services: Add missing files in the wheel

4.2.4
-----

- Skydive: Fix topology discovery
- Doc: Fix ``pattern_hosts`` kwargs

4.2.3
-----

- Doc: Factorize readme and doc index

4.2.2
-----

- Doc: Fix sphinx warnings

4.2.1
-----

- Fix changelog syntax

4.2.0
-----

- Service: Add skydive service
- Service: Internal refactoring

4.1.1
-----

- Catch-up changelog for 4.1.x


4.1.0
-----

- API(breaks): Introduce ``patterns_hosts`` as a keyword argument
- API: Introduce ``gather_facts`` function
- Doc: Fix python3 for virtualenv on g5k
- API: Allow top level and module level arguments to be passed
  in ``run_command`` and ``play_on``
- G5K: Use ring to cache API requests results
- API: Support for ``raw`` module in ``play_on``
- Black formatting is enforced

4.0.3
-----

- Doc: Fix netem service link

4.0.2
-----

- Doc: Add a placement example (vmong5k)

4.0.1
-----

- Doc: Capitalize -> EnOSlib

4.0.0
-----

- Service: add Netem service as a replacement for ``(emulate|reset|validate)_network`` functions.
  Those functions have been dropped
- Service: add Docker service. Install the docker agent on all your nodes and
  optionally a docker registry cache
- Upgrade jsonschema dependency
- Migrate sonarqube server
- Vagrant: OneOf for ``flavour`` and ``flavour_desc`` has been fixed
- Api: ``play_on`` tasks now accept a ``display_name`` keyword. The string will
  be displayed on the screen as the name of the command.

3.4.2
-----

- Service: fix example

3.4.1
-----

- Service: monitoring update doc

3.4.0
-----

- Introduce a monitoring service (quickly deploy a monitoring stack)
- API: Add `display_name` kwargs in `play_on` (debug/display purpose)

3.3.3
------

- Doc: in using-tasks include whole python script

3.3.2
------

- Doc: fix using-tasks output

3.3.1
------

- Doc: Include changelog in the documentation
- ChameleonBaremetal: fix tutorial


3.3.0
------

- G5k: automatic redepoy (max 3) when nodes aren't deployed correctly

3.2.4
------

- Avoid job_name collision from 2 distinct users

3.2.3
------

- Fix an issue with emulate_network (it now uses `inventory_hostname`)

3.2.2
------

- VMonG5k: fix the networks returned value

3.2.1
------

- G5k: Fix static driver

3.2.0
------

- VMonG5K: Enables taktuk for image broadcast

3.1.4
------

- Doc: Fix network_emulation conf

3.1.3
------

- Doc: add missing files

3.1.2
------

- Doc: Document network emulation

3.1.1
------

- Doc: VMonG5K warning about the `working_dir` being removed

3.1.0
------

- VMonG5k: expose `start_virtualmachines` function

3.0.1
------

- Doc: Add VMonG5k primer
- Doc: Secure credential file

3.0.0
------

- [G5k]: now uses python-grid5000 for all the interactions with Grid'5000
- [VMonG5K]: Add a gateway option
- [VMonG5K]: Coerce to `enoslib.Host` before returning from init.

2.2.10
------

- Doc: use std env for primer on g5k

2.2.9
------

- Doc add 10.1109/TPDS.2019.2907950

2.2.8
------

- Dependencies: add pyyaml and be a bit strict
- tasks: add the knowledge of host datastructure when deserializing
- Vagrant: force gateway ip to string
- Doc: add performance tuning section

2.2.7
------

- Doc: Gender equality fix

2.2.6
------

- Doc: static provider
- Doc: various fixes

2.2.5
------

- CI: add `play_on` functional test

2.2.4
------

- Doc: Update Primer (add g5k example)

2.2.3
------

- API: fix `gather_facts=False` in `play_on`

2.2.2
------

- Doc: put project boostrap at the end (formerly quickstart)

2.2.1
------

- Doc: add EnOSlib primer
- API: discover_network now add `<network>_ip` and `<network>_dev` in the hosvars

2.2.0
------

- API: Introduce `play_on` context_manager to describe a playbook directly from python

2.1.0
------

- API: In memory inventory. Generating a inventory file is not mandatory anymore.
       On can pass the provider roles in most of the API calls.
- VMonG5K: allow to specify a working directory
- Dependencies: Upgrade Ansible to latest stable (2.7.x)

2.0.2
------

- (breaking) VMonG5K/Vagrant: Unify code. `flavour_desc` dict can be used after
  building the MachineConfiguration.

2.0.1
------

- VMonG5K: Package was missing site.yml file

2.0.0
------

Warning breaking changes:

- EnOSlib is python3.5+ compatible exclusively.

- Provider: a provider must be given a configuration object. You can build it
  from a dictionnary (this mimics EnOSlib 1.x) or build it programmaticaly. In
  pseudo code, changes are needed in your code as follow:
  ```
  from enoslib.infra.enos_g5k.configuration import Configuration
  from enoslib.infra.enos_g5k.provider import G5k
  ...
  conf = Configuration.from_dictionnary(provider_conf)
  g5k = G5k(conf)
  ...
  ```

- Provider: Configuration object
  The configuration object aim at ease the process of building configuration for
  providers. It can be validated against a jsonschema defined for each provider.
  Validation is implicit using `from_dictionnary` or explicit using the
  `finalize()` method of the configuration.

- Doc: Update docs to reflect the above

- VMonG5K: new provider that allows to start virtual machines on G5K.

1.12.3
------

- API: `utils.yml` playbook now forces fact gahering.
- Misc: initial gitlab-ci supports

1.12.2
------

- G5K: Refix an issue when number of nodes is zero

1.12.1
------

- G5K: fix an issue when number of nodes is zero

1.12.0
------

- API: `emulate|reset|validate` now accept an extra_vars dict
- G5K: `secondary_networks` are now a mandatory key
- G5K: support for zero nodes roles

1.11.2
------

- Make sure role and roles are mutually exclusive

1.11.1
------

- Fix empty `config_file` case in enostask

1.11.0
------

- G5K: add static oar job support

1.10.0
------

- G5K: align the subnet description with the other network
- API: validate_network now filters devices without ip address
- API: check_network now uses JSON serialisation to perform better

1.9.0
------

- G5K api: expose get_clusters_sites
- G5K: dhcp is blocking
- G5k: introduce drivers to interact with the platform

1.8.2
------

- Chameleon: fix flavor encoding
- Chameleon: Create one reservation per flavor
- Openstack: fix python3 compatibility

1.8.1
------

- relax openstack client constraints

1.8.0
------

- G5K api: expose exec_command_on_nodes
- Openstack: enable the use of session for blazar
- Openstack: Allow keystone v3 authentification

1.7.0
------

- G5K api: fixed get_clusters_interfaces function
- Ansible: group vars were'nt loaded
- Allow fake interfaces to be mapped to net roles

1.6.0
------

- G5K: add subnet support
- An enostask can now returns a value
- Openstack/Chameleon: support region name
- Openstack/Chameleon: support for extra prefix for the resources
- Chameleon: use config lease name

1.5.0
------

- python3 compatibility
- Confirm with predictable NIC names on g5k

1.4.0
------

- Fix the autodoc generation
- Document the cookiecutter generation
- Default to debian9 for g5k

1.3.0
------

- Change setup format
- Move chameleon dependencies to extra_require

1.2.1
------

- Drop validation of the bandwitdh
- Add missing host file

1.2.0
------

- Add reset network


0.0.6
------

- add `min` keyword in machine descipriotn on for G5K

0.0.5
------

- reservation is supported in g5k provider
- `expand_groups` is available in the api
- `get_cluster_interfaces` is available in the g5k api.

0.0.4
------

- Exclude not involved machines from the tc.yml run
- Take force_deploy in g5k provider
- Wait ssh to be ready when `check_network=True` in `generate_inventory`
- Add start/end enostask logging

0.0.3
------

- Add static provider
- Add OpenStack provider (and chameleon derivatives)
- Add `provider_conf` validation
- Rearchitect providers
- Add dummy functionnal tests
- Add network emulation

0.0.2
------

- Add fake interface creation option un check_network
- Encapsulate check_network in generate_inventory
- Add automatic discovery of network interfaces names/roles
- Add vagrant/g5k provider

0.0.1
------

- Initial version
