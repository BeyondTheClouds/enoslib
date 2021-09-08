⚒️ Changelog
============

7.0.0
-----

- Introduce a way to configure the library.
  For now this can be used to control the cache used when accessing the G5k API.
- Jupyter integration
    - Provider configuration, roles and networks can be displayed in a rich format in a jupyter notebook
    - svc/locust: can display some information
- api/objects: introduce ``RolesLike`` type: something that looks like to some
    remote machines.  More precisely, it's a Union of some types: a ``Host``, a list
    of Host or a plain-old ``Roles`` datastructure. It's reduce the number of
    function of the API since function overloading isn't possible in Python.
- api:run_command: can now use ``raw`` connections (no need for python at the dest)
- api: introduce `bg_start`, `bg_stop` that generates the command for
  starting/stopping backgroung process on the remote nodes.
- api: introduce `background` keyword. It serves the same purpose of
  `bg_start/end` but is more generic in the sense that many modules can benefit
  from the keyword and it doesn't have any dependencies. Under the hood this will
  generate an async Ansible tasks with infinite timeout.
- svc/dstat: make it a context manager, adapt the examples
- svc/tcpdump: make it a context manager, adapt the examples
- svc/locust: update to the latest version. align the API to support parameter-less ``deploy`` method
    (run ``headless`` by default)
- Doc: they-use-it updated


6.2.0
-----

- svc/docker: now installs `nvidia-container-toolkit` if deemed relevant (on
  nodes that have a NVidia GPU card).
- svc/monitoring: now configures an `nvidia-smi` input on nodes that have a
  NVidia GPU card and the nvidia container runtime. Add an example to show how to
  make both service together to get some GPU metrics in the collector.
- docs: fixed missing network selection in ``tuto_svc_netem_s.py``
- jinja2 3.x compatibility

Possibly breaking:

- We've relaxed the Ansible version that is pulled when installing EnOSlib.
  Version ranging from Ansible 2.9 to Ansible 4 (excluded) are now accepted.
  There's a potential risk that some corner cases are broken (nothing bad has been
  detected though ... 🤞)
  This was necessary to get benefit from the latest modules version.
  EnOSlib can benefit from any (third party or updated core) collections
  installed locally.

6.1.0
-----

Breaking:

- svc/netem-htb: Rework on the various service APIs. Now the user can use a
    builder pattern to construct its network topology with Netem and NetemHTB.
    Check the examples to see how it looks like. Unfortunately this breaks the
    existing APIs.

Misc:

- provider: Openstack provider fixed
- api: add ``run_once`` and ``delegate_to`` keywords
- api: add ``populate_keys`` that populate ssh keys on all hosts (use case:
  MPI applications that needs to all hosts to be ssh reachable)
- tasks: env implements ``__contains__`` (resp. ``setdefault``) to check if a
  key is in the env (resp. set a default value) (cherry-pick from 5.x)
- svc/monitoring: remove the use of explicit ``become`` in the deployment

6.0.4
-----

- svc/docker: allow to specify a port (cherry-pick from 5.x)
- doc: fix typo  + some improvements (emojis)
- api/play_on: now accepts an Ansible Inventory (cherry-pick from 5.x)

5.5.2
-----

- svc/docker: allow to specify a port

6.0.3
-----

- svc:netem: fix an issue with missing self.extra_vars
- svc:monitoring: stick to influxdb < 2 for now (influxdb2 requires an auth)

6.0.2
-----

Doc/G5k: Add an example that makes use of the internal docker registries of
         Grid'5000

6.0.1
-----

Doc: install instructions on the front page
Doc/G5k: Document G5kTunnel

6.0.0 (the IPv6 release and plenty other stuffs)
------------------------------------------------

- Beware this versions has breaking changes in various places
- Networks from the various providers deserved a true abstraction: it's done.

  - ``provider.init`` now returns two similar data structures: Compute roles
    (aka ``roles``) and networks roles (``aka networks``). Both are
    dictionnaries of ``Host`` (resp. ``Networks``) indexed by the user provided
    tags.

  - Networks returned by a provider encompass IPv4 and IPv6 networks. User
    can filter them afterwards based on the wanted type.
    For instance a user reserving a vlan on Grid'5000 will be given two networks
    corresponding to the IPv4 kavlan network and its IPv6 counterpart.

  - Most of services have been updated to support the above change.

- Introduce ``enoslib.objects`` to organise library level objects. You'll
  find there ``Host`` and ``Network`` data structure and some other objects definitions.

- ``Host`` now have a ``net_devices`` and ``processor`` attributes. These
  attributes is populated by ``sync_info`` API function with the actual network
  devices information (IPv4/IPv6 addresses, device type...) and processor
  information.

- ``Host`` now have a ``processor`` attribute. This attribute is populated by
  ``sync_info`` API function with the actual processor information (number of
  cores, number of threads...)

- Netem service has been split in two parts. First, you can enforce in and
  out limitations on remote NIC cards (see ``netem`` module). Ingress
  limitations use virtual ifbs. Second do the same but allow to add filters
  (based on Hierarchical Token Bucket) on the queuing discipline to set
  heterogeneous limitations on a single NIC card (see ``htb`` module).

- API: ``discover_networks`` is now ``sync_info`` as it syncs more than networks.

- API: ``wait_for`` is the new name for ``wait_ssh``. The rationale is that
  we actually defer the connection to one Ansible plugin (which may or may not
  be the SSH plugin)

- API: ``run_ansible`` implements a retry logic independent to the connection
  plugin used.

- API: functions that calls ``run_ansible`` now accepts keyword arguments
  that are passed down the stack (instead of being explicit). This includes
  ``extra_vars``ansible_retries``.

- Introduce ``enoslib.docker`` module to manage docker containers as first
  class citizens. In particular, ``DockerHost`` is a specialization of
  ``Host``.

- Introduce ``enoslib.local`` to manage the local machine as an EnOSlib host.

- Providers: Any provider can now be used using a context manager. The
  resources will be release when leaving the context.

- Documentation has been reorganized and now uses a new theme (pydata-sphinx-theme)

- Note that the Openstack provider is broken currently.

5.5.4
-----

- tasks: env implements ``__contains__`` (resp. ``setdefault``) to check if a
  key is in the env (resp. set a default value)

5.5.3
-----

- api: ``play_on`` can be called with an inventory file


5.5.2
-----

- svc/docker: allow to specify a port

5.5.1
-----

- G5k: support for ``exotic`` job type. If you want to reserve a node on
  exotic hardware, you can pass either ``job_type=[allow_classic_ssh, exotic]``
  or ``job_type=[deploy, exotic]``. Passing a single string to ``job_type`` is
  also possible (backward compatibility)

5.5.0
-----

-  	🎉 New provider	🎉: Iotlab provides resources on https://www.iot-lab.info/.

  - Reserve nodes and run some actions (radio monitoring, power consumption, run modules on A8 nodes)

  - Connection between Grid'5000 and Fit:

    - Using Grid'5000 VPN: allow bi-redirectionnal communication over IPv4

    - Using IPv6: allow transparent communication between both platform (limitation: connection established from Fit to G5k are currently dropped)

- Monitoring Service:

    - The monitoring stack can span both Grid'5000 (ui, collector, agents) and Fit platform (agents only).

-✨ New Dask Service ✨: Deploy a Dask cluster on your nodes.

    - Replace the former Dask Service and allow for on demand computation (*just in time* deployment.)

    - Example updated accordingly

- G5k: G5kTunnel context manager to automatically manage a tunnel from your current machine to Grid'5000 machines.

Older versions
---------------

5.4.3
~~~~~

- G5k: returned Host.address was wrong when using vlans
- Doc: fix execo url

5.4.2
~~~~~

- Doc: G5k change tutorial URL
- G5k: Align the code with the new REST API for vlans (need python-grid5000 >= 1.0.0)

5.4.1
~~~~~

- Service/docker: swarm support

5.4.0
~~~~~

- Support ``from enoslib import *``
- G5k: surgery in the provider: dictectomy.
    - extra: allow job inspection through ``provider.hosts`` and ``provider.networks``
- G5k: reservation at the server level is now possible
    Use case: you need a specific machine (or certain number of machines over a specific set of machines)
- G5k: configuration can take the project as a key
- Doc: G5k uniformize examples

5.3.4
~~~~~

- G5k: make the project configurable (use the project key in the
  configuration)

5.3.3
~~~~~

- G5k: fix an issue when dealing with global vlans

5.3.2
~~~~~

- VMonG5k: resurrect nested kvm

5.3.1
~~~~~

- Doc: Add E2Clab

5.3.0
~~~~~

- Service/dstat: migrate to ``dool`` as a ``dstat`` alternative
- Fix Ansible 2.9.11 compatibility

5.2.0
~~~~~

- Api: Add ``get_hosts(roles, pattern_hosts="all")`` to retrieve a list of host matching a pattern
- Doc: Fix netem example inclusion


5.1.3
~~~~~

- Tasks: Fix an issue with predefined env creation
- Service/dstat: Fix idempotency of deploy

5.1.2
~~~~~

- Tasks: automatic ``env_name`` change to remove colons from the name

5.1.1
~~~~~

- Netem: Better support for large deployment (introduce `chunk_size` parameter)

5.1.0
~~~~~

- Tasks:
    - review the internal of the implementation
    - support for nested tasks added
- Doc:
    - Add autodoc summary in the APIs pages (provided by autodocsumm)
    - Align some examples with the new Netem implementation

5.0.0
~~~~~

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
~~~~~~

- Service/docker:
    - Allow to mount the whole docker dir elsewhere
      (e.g in /tmp/docker instead of /var/lib/docker)
    - Default to registry:None, meaning that this will
      deploy independent docker daemons

4.10.1
~~~~~~

- Service/dstat: doc
- service/monitoring: typecheck


4.10.0
~~~~~~

- Service/dstat: add a new dstat monitoring
- Doc: some fixes (comply with the discover_networks)

4.9.4
~~~~~

- Doc: some fixes

4.9.3
~~~~~

- Doc: some fixes / add a ref

4.9.2
~~~~~

- Doc: add some refs in they-use-it.rst

4.9.1
~~~~~

- Fix: include the missing BREAKING change of 4.9.0

4.9.0
~~~~~~

- Doc: Add a ref
- Service/locust: Fix density option
- Service/Netem: support for bridged networks
- Api/BREAKING: `discover_networks` doesn't have side effects anymore on the hosts.

4.8.12
~~~~~~

- Doc: Simplify network emulation example

4.8.11
~~~~~~

- VMonG5K: Don't fail if #pms > #vms
- Doc: add madeus-openstack-benchmarks
- Service/locust: review, add a density option that controls
  the number of slave to start on each node.
- Doc: Expose the Locust documentation

4.8.10
~~~~~~

- Service/monitoring: allow for some customisations
- VMonG5K: use the libvirt directory for all the operations

4.8.9
~~~~~

- Service/netem: fix validate when network is partitioned

4.8.8
~~~~~

- Doc: Add content for quick access
- Doc: Add parameters sweeper tutorial

4.8.7
~~~~~

- Doc: clean and use continuation line
- Service/docker: remove useless statement

4.8.6
~~~~~

- Api/play_on: don't gather facts twice
- VMonG5k: 🐎 enable virtio for network device 🐎
- Service/monitoring: add the influxdb datasource automatically

4.8.5
~~~~~

- Api: Introduce ``ensure_python[2,3]`` to make sure python[2,3]
  is there and make it the default version (optionally)
- Api: ``wait_ssh`` now uses the raw module
- Api: rename some prior with a double underscore (e.g. ``__python3__``)

4.8.4
~~~~~

- Doc: Handling of G5k custom images
- Host: Implementation of the __hash__() function
- API: ``play_on`` offers new strategies to gather Ansible facts
- type: Type definitions for Host, Role and Network

4.8.3
~~~~~

- G5K/api: job_reload_from_name fix for anonymous user
- Doc: some cleaning, advertise mattermost channel

4.8.2
~~~~~

- VMonG5K: some cleaning
- Host: copy the passed extra dict
- Skydive: fix docstring

4.8.1
~~~~~

- Service/Monitoring: fix collector_address for telegraf agents

4.8.0
~~~~~

- Enforce python3.6+ everywhere
- Add more functionnal tests
- Api: ``play_on`` accepts a ``priors`` parameters
- Add ``run`` command for simplicity sake
- ``enoslib.host.Host`` is now a dataclass
- Typecheck enabled in CI

4.7.0
~~~~~

- G5k: Default to Debian10
- Vagrant: Defaut to Debian10
- VMonG5k:
    - Default to Debian10
    - Activate VLC console (fix an issue with newest G5K virt images...)
    - Run VMs as root

4.6.0
~~~~~

- Chameleon: minor fixes, support for the primer example
- Vagrant: customized name and config is now supported
- Locust/service: initial version (locust.io)
- G5k: support for arbitrary SSH key

4.5.0
~~~~~

- Dependencies: upgrade python-grid5000 to 0.1.0+
- VMonG5K/API break: use g5k api username instead of USER environment variable
- VMonG5K: make the provider idempotent

4.4.5
~~~~~

- Doc: some fixes
- VMonG5k: change gateway description

4.4.4
~~~~~

- Doc: distem makes use of stretch image by default

4.4.3
~~~~~

- Doc: Doc updates (readme and distem)

4.4.2
~~~~~

- Doc: update distem tutorial

4.4.1
~~~~~

- Catch up changelog

4.4.0
~~~~~

- New provider: Distem

4.3.1
~~~~~

- G5k: fix walltime > 24h

4.3.0
~~~~~

- G5k: ``get_api_username`` to retrieve the current user login
- Doc: fix ``play_on``

4.2.5
~~~~~

- Services: Add missing files in the wheel

4.2.4
~~~~~

- Skydive: Fix topology discovery
- Doc: Fix ``pattern_hosts`` kwargs

4.2.3
~~~~~

- Doc: Factorize readme and doc index

4.2.2
~~~~~

- Doc: Fix sphinx warnings

4.2.1
~~~~~

- Fix changelog syntax

4.2.0
~~~~~

- Service: Add skydive service
- Service: Internal refactoring

4.1.1
~~~~~

- Catch-up changelog for 4.1.x


4.1.0
~~~~~

- API(breaks): Introduce ``patterns_hosts`` as a keyword argument
- API: Introduce ``gather_facts`` function
- Doc: Fix python3 for virtualenv on g5k
- API: Allow top level and module level arguments to be passed
  in ``run_command`` and ``play_on``
- G5K: Use ring to cache API requests results
- API: Support for ``raw`` module in ``play_on``
- Black formatting is enforced

4.0.3
~~~~~

- Doc: Fix netem service link

4.0.2
~~~~~

- Doc: Add a placement example (vmong5k)

4.0.1
~~~~~

- Doc: Capitalize -> EnOSlib

4.0.0
~~~~~

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
~~~~~

- Service: fix example

3.4.1
~~~~~

- Service: monitoring update doc

3.4.0
~~~~~

- Introduce a monitoring service (quickly deploy a monitoring stack)
- API: Add `display_name` kwargs in `play_on` (debug/display purpose)

3.3.3
~~~~~~

- Doc: in using-tasks include whole python script

3.3.2
~~~~~~

- Doc: fix using-tasks output

3.3.1
~~~~~~

- Doc: Include changelog in the documentation
- ChameleonBaremetal: fix tutorial


3.3.0
~~~~~~

- G5k: automatic redepoy (max 3) when nodes aren't deployed correctly

3.2.4
~~~~~~

- Avoid job_name collision from 2 distinct users

3.2.3
~~~~~~

- Fix an issue with emulate_network (it now uses `inventory_hostname`)

3.2.2
~~~~~~

- VMonG5k: fix the networks returned value

3.2.1
~~~~~~

- G5k: Fix static driver

3.2.0
~~~~~~

- VMonG5K: Enables taktuk for image broadcast

3.1.4
~~~~~~

- Doc: Fix network_emulation conf

3.1.3
~~~~~~

- Doc: add missing files

3.1.2
~~~~~~

- Doc: Document network emulation

3.1.1
~~~~~~

- Doc: VMonG5K warning about the `working_dir` being removed

3.1.0
~~~~~~

- VMonG5k: expose `start_virtualmachines` function

3.0.1
~~~~~~

- Doc: Add VMonG5k primer
- Doc: Secure credential file

3.0.0
~~~~~~

- [G5k]: now uses python-grid5000 for all the interactions with Grid'5000
- [VMonG5K]: Add a gateway option
- [VMonG5K]: Coerce to `enoslib.Host` before returning from init.

2.2.10
~~~~~~

- Doc: use std env for primer on g5k

2.2.9
~~~~~~

- Doc add 10.1109/TPDS.2019.2907950

2.2.8
~~~~~~

- Dependencies: add pyyaml and be a bit strict
- tasks: add the knowledge of host datastructure when deserializing
- Vagrant: force gateway ip to string
- Doc: add performance tuning section

2.2.7
~~~~~~

- Doc: Gender equality fix

2.2.6
~~~~~~

- Doc: static provider
- Doc: various fixes

2.2.5
~~~~~~

- CI: add `play_on` functional test

2.2.4
~~~~~~

- Doc: Update Primer (add g5k example)

2.2.3
~~~~~~

- API: fix `gather_facts=False` in `play_on`

2.2.2
~~~~~~

- Doc: put project boostrap at the end (formerly quickstart)

2.2.1
~~~~~~

- Doc: add EnOSlib primer
- API: discover_network now add `<network>_ip` and `<network>_dev` in the hosvars

2.2.0
~~~~~~

- API: Introduce `play_on` context_manager to describe a playbook directly from python

2.1.0
~~~~~~

- API: In memory inventory. Generating a inventory file is not mandatory anymore.
       On can pass the provider roles in most of the API calls.
- VMonG5K: allow to specify a working directory
- Dependencies: Upgrade Ansible to latest stable (2.7.x)

2.0.2
~~~~~~

- (breaking) VMonG5K/Vagrant: Unify code. `flavour_desc` dict can be used after
  building the MachineConfiguration.

2.0.1
~~~~~~

- VMonG5K: Package was missing site.yml file

2.0.0
~~~~~~

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
~~~~~~

- API: `utils.yml` playbook now forces fact gahering.
- Misc: initial gitlab-ci supports

1.12.2
~~~~~~

- G5K: Refix an issue when number of nodes is zero

1.12.1
~~~~~~

- G5K: fix an issue when number of nodes is zero

1.12.0
~~~~~~

- API: `emulate|reset|validate` now accept an extra_vars dict
- G5K: `secondary_networks` are now a mandatory key
- G5K: support for zero nodes roles

1.11.2
~~~~~~

- Make sure role and roles are mutually exclusive

1.11.1
~~~~~~

- Fix empty `config_file` case in enostask

1.11.0
~~~~~~

- G5K: add static oar job support

1.10.0
~~~~~~

- G5K: align the subnet description with the other network
- API: validate_network now filters devices without ip address
- API: check_network now uses JSON serialisation to perform better

1.9.0
~~~~~~

- G5K api: expose get_clusters_sites
- G5K: dhcp is blocking
- G5k: introduce drivers to interact with the platform

1.8.2
~~~~~~

- Chameleon: fix flavor encoding
- Chameleon: Create one reservation per flavor
- Openstack: fix python3 compatibility

1.8.1
~~~~~~

- relax openstack client constraints

1.8.0
~~~~~~

- G5K api: expose exec_command_on_nodes
- Openstack: enable the use of session for blazar
- Openstack: Allow keystone v3 authentification

1.7.0
~~~~~~

- G5K api: fixed get_clusters_interfaces function
- Ansible: group vars were'nt loaded
- Allow fake interfaces to be mapped to net roles

1.6.0
~~~~~~

- G5K: add subnet support
- An enostask can now returns a value
- Openstack/Chameleon: support region name
- Openstack/Chameleon: support for extra prefix for the resources
- Chameleon: use config lease name

1.5.0
~~~~~~

- python3 compatibility
- Confirm with predictable NIC names on g5k

1.4.0
~~~~~~

- Fix the autodoc generation
- Document the cookiecutter generation
- Default to debian9 for g5k

1.3.0
~~~~~~

- Change setup format
- Move chameleon dependencies to extra_require

1.2.1
~~~~~~

- Drop validation of the bandwitdh
- Add missing host file

1.2.0
~~~~~~

- Add reset network


0.0.6
~~~~~~

- add `min` keyword in machine descipriotn on for G5K

0.0.5
~~~~~~

- reservation is supported in g5k provider
- `expand_groups` is available in the api
- `get_cluster_interfaces` is available in the g5k api.

0.0.4
~~~~~~

- Exclude not involved machines from the tc.yml run
- Take force_deploy in g5k provider
- Wait ssh to be ready when `check_network=True` in `generate_inventory`
- Add start/end enostask logging

0.0.3
~~~~~~

- Add static provider
- Add OpenStack provider (and chameleon derivatives)
- Add `provider_conf` validation
- Rearchitect providers
- Add dummy functionnal tests
- Add network emulation

0.0.2
~~~~~~

- Add fake interface creation option un check_network
- Encapsulate check_network in generate_inventory
- Add automatic discovery of network interfaces names/roles
- Add vagrant/g5k provider

0.0.1
~~~~~~

- Initial version
