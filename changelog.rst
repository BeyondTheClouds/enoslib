⚒️ Changelog
============

.. _v8.1.6:

8.1.6
-----

Fixed
+++++

- **Chameleon:** Constrain OpenStack dependencies to maintain Python 3.7 compatibility
- **G5K:** Fix missing nodes in deploy edge case
- **G5K:** Fix env_version handling, it was only applied when force_deploy is true
- **G5K:** Fix ``inside_g5k`` method to detect usage from a machine inside G5K network.
- **G5K:** Make site listing aware of excluded sites
- **Monitoring service:** Fix crash when nodes have multiple IPv6 addresses


.. _v8.1.5:

8.1.5
-----

Added
+++++

- **Dependencies:** Allow minor version updates of Ansible

Fixed
+++++

- **G5k:** Fix race condition when destroying and reloading jobs
- **VMonG5K:** Make VM to host allocation deterministic
- **AccurateNetemHTB:** Improve error message when the computed latency is negative


.. _v8.1.4:

8.1.4
-----

Added
+++++

- **VMonG5K:** Add new parameter :ref:`vcore_type <vmong5k-schema>` to give more
  control on the VM allocation algorithm. By default, it allocates vCPUs based on
  the number of physical hyper-threads.

Fixed
+++++

- **G5k**: Fix number of cores for multi-CPU nodes
- **G5K**: Fix DHCP at end of deployment when python interpreter is not found
- **All**: Remove python3 interpreter override. This allows to support CentOS nodes.
  It might change the python interpreter to python2 for old Ansible versions (2.9, 2.10, 3, 4)
- **Packaging**: Remove runtime dependency on setuptools


.. _v8.1.3:

8.1.3
-----

Fixed
+++++

- **G5k**: ``G5KTunnel`` can be given a local port
- **VMonG5K**: Fix time in the VM


.. _v8.1.2:

8.1.2
-----

Fixed
+++++

- **Docker**: support Docker v23 deployment

.. _v8.1.1:

8.1.1
-----

Fix: multisites deployment

.. _v8.1.0:

8.1.0
-----

Added
+++++

- **G5K:** automatically use ``access.grid5000.fr`` to avoid needing a local SSH config (can be disabled using the config)
- **G5K:** allow to deploy a :ref:`specific version of an environment <grid5000-schema>`
- **Docker:** allow to :doc:`login to Docker hub </apidoc/docker>` (to access private images or to bypass rate-limiting)
- **K3S:** allow to :doc:`specify which version to install </apidoc/k3s>`

Fixed
+++++

- **K3S:** fix setup for K3S >= 1.24

Changed
+++++++

- Big typing improvements
- Enforce ``isort`` pre-commit hook
- Advertise support for Ansible 7

.. _v8.0.0:

8.0.0
-----

Added
+++++

- 🚀 :doc:`Chameleon Edge provider </tutorials/chameleon>`
- 🚀 :py:class:`~enoslib.infra.providers.Providers`: a provider that can sync resources on multiple platforms

General changes
+++++++++++++++

- Python 3.10 support
- Introduce provider-specific pip packages to make dependencies
  optional. The base ``enoslib`` package now only supports Grid'5000, but
  you can install the following pip package variants:
  ``enoslib[vagrant]``, ``enoslib[chameleon]``, ``enoslib[iotlab]``,
  ``enoslib[distem]``, or ``enoslib[all]`` for everything.
- Increase the supported Ansible version range (>=2.9,<=6.3)

New providers features
++++++++++++++++++++++

- **g5k:** use standard Grid'5000 environment by default instead of deploying
  a ``debian11-nfs`` image:

  - this is the same behaviour as the (now deprecated)
    ``allow_classic_ssh`` job type
  - this new default behaviour is much faster to provision and matches the
    behaviour of native Grid'5000 tools
  - however, this might impact your experiments because the standard
    environment comes with many more tools than ``debian11-nfs``
  - if you want accurate control on the software environment, you should
    always use the ``deploy`` job type

- **g5k:** env name is now required when using the ``deploy`` job type
- **g5k:** simplify configuration by auto-configuring primary network if not specified
- **g5k:** :ref:`add support <g5k_reservable_disks>` for `reservable disks <https://www.grid5000.fr/w/Disk_reservation>`_
- **g5k:** :py:meth:`provider.destroy() <enoslib.infra.enos_g5k.provider.G5kBase.destroy>` can now wait for a state change (use ``wait=True``)
- **g5k:** expose the jobs through the :py:attr:`provider.jobs <enoslib.infra.enos_g5k.provider.G5kBase.jobs>` property
- **g5k:** Introduce :py:func:`~enoslib.infra.enos_g5k.g5k_api_utils.enable_home_for_job` and :py:func:`~enoslib.infra.enos_g5k.g5k_api_utils.enable_group_storage` to allow to mount NFS storage provided by Grid'5000 (either user home or a group storage)
- **g5k:** Add support for ``container`` OAR job types.
- **g5k:** Add support for ``besteffort`` OAR queue.
- **vmong5k:** support multisite deployment.

Providers fixes
+++++++++++++++

- **g5k:** fix global kavlan configuration: when a node was located on another
  site as the global kavlan network, it was not actually put in the kavlan
  network (calls to the Kavlan API were silently failing).
- **g5k:** fix missing nodes in roles when using multi-sites deployments
- **g5k:** use new Providers mechanism for multi-sites reservations.  This
  fixes several issues with multi-sites experiments:

  - only relevant sites are queried
  - partial job reloading now works as expected (e.g. reloading a job on
    one site while creating a new job on another site)

- **g5k:** fix an issue on the reservation date preventing multisite deployment
- **g5k:** reduce number of log entries printed at the info level
- **g5k:** fix misleading deployment logging

Services
++++++++

- **Netem:** Introduce :py:class:`~enoslib.service.emul.htb.AccurateNetemHTB` to apply more accurate network latency between node.
  This takes into account the physical delay of targeted paths
- **NetemHTB:** add support for constraints on IPv6 addresses
- **NetemHTB:** loss parameter is explicitly a percentage
- **Netem:** Introduce ``fping_stats`` static method to read from the backuped
  file easily after a call to ``validate``.
- **k3s:** refresh service (deploy the dashboard automatically)

Library
+++++++

- **api:** change :py:func:`~enoslib.api.ensure_python3` to pull fewer
  Debian packages (only ``python3`` itself)
- **api:** change default behaviour of
  :py:func:`~enoslib.api.ensure_python3` to no longer create a ``python ->
  python3`` symlink by default.
- **api:** add :py:func:`~enoslib.check` function to validate basic functionality of Enoslib
- **api:** :py:func:`~enoslib.api.actions` can now take fqdn names (e.g. ``ansible.builtin.shell``).
  This allows for using any third party Ansible modules.
- **api:** :py:func:`~enoslib.api.actions`  can now takes the top-level ``vars`` options.
- **Host:** expose :py:meth:`~enoslib.objects.Host.get_extra`,
  :py:meth:`~enoslib.objects.Host.set_extra`, and
  :py:meth:`~enoslib.objects.Host.reset_extra` methods to manipulate the
  extra vars of the host.
- Remove warning about empty host list (Ansible>=2.11 only)

Documentation
+++++++++++++

- **vmong5k:** document :ref:`how to mount home directory or group storage
  on the VMs <vmong5k_home_directory>`
- **chameleon:** update chameleon tutorial with an :doc:`edge-to-cloud example </tutorials/chameleon>`
- **g5k:** update all :doc:`Grid'5000 tutorials </tutorials/grid5000>` to be
  more progressive and to showcase new features
- **enoslib-tutorials** is now a standalone repo (imported as submodule here)
- **they-use-it:** add hal-03654722, 10.1109/CCGrid54584.2022.00084

Internals
+++++++++

- **all:** Provider(s) can now take a name
- **all:** introduce ``test_slot``, ``set_reservation`` at the interface level
  (prepare multi-provider experiment).  This will test if a slot (time x
  resource) can be started on the corresponding platform
- **iotlab:** Implement ``test_slot`` (non naïve implementation)
- **g5k:** Implement ``test_slot`` (non naïve implementation)
- **g5k:** remove Execo dependency
- **CI:** use pylint and type checking to improve static analysis


.. _v7.2.1:

7.2.1
-----

- jupyter is an optional dependency (if you want to have rich output)
  ``pip install enoslib[jupyter]``


.. _v7.2.0:

7.2.0
-----

- Upgrade and relax Ansible possible versions (from 3.X to 5.X)
- API: fix a wrong inheritance that prevents ``stdout_callback`` to be taken into account.
- Config: Introduce ``pimp_my_lib`` boolean config key to enforce a special
  stdout_callback based on `rich <https://github.com/Textualize/rich>`_. The
  rationale is to have nicer and more compact outputs for Ansible tasks (e.g.
  ``api.actions`` and ``api.run*``)
- Add an optional dependency ``jupyter`` to install extra library dedicated to
  running EnOSlib from Jupyter.
- API: Introduce an ``init_logging`` function: setup a good-enough logging mecanism.
- Config: add a ``dump_results`` key to enable remote actions result collection
  in a file.
- Dstat: add an ``to_pandas`` static method to load all the metrics previously
  backuped to pandas. This avoids to know the internal directory structures
  EnOSlib uses.
- VMonG5K: Allow to specify the domain type (``kvm`` for hardware assisted
  virtualizaton / ``qemu`` full emulation mode)
- VMonG5K: Allow to specify a reservation date


.. _v7.1.2:

7.1.2
-----

- IOTlab: support for RPI3 added
- G5k: firewall context manager clean the firewall rules when an exception is
  raised.
- Conda: introduce ``conda_from_env`` to infer conda prefix location and current
  environment from environmental variables
- Docker: adapt to debian11


.. _v7.1.1:

7.1.1
-----

- api: `Results` exposes a `to_dict` method (purpose is to json serialize)


.. _v7.1.0:

7.1.0
-----

- G5k: add reconfigurable firewall facilities (see provider doc). This
  allows to create an opening rule and delete it later.
- api: custom stdout callback is now use as a regular plugin.  This allows
  to confgure the stdout plugin using the Ansible configuration file


.. _v7.0.1:

7.0.1
-----

- svc/skydive: update to new Roles datastructure


.. _v7.0.0:

7.0.0
-----

- Introduce a way to configure the library.
  For now this can be used to control the cache used when accessing the G5k API.
- Jupyter integration
    - Provider configuration, roles and networks can be displayed in a rich format in a jupyter notebook
    - There is an ongoing effort to port such integration in various part of the library
- api/objects: introduce ``RolesLike`` type: something that looks like to
  some remote machines.  More precisely, it's a Union of some types: a
  ``Host``, a list of Host or a plain-old ``Roles`` datastructure. It's
  reduce the number of function of the API since function overloading
  isn't possible in Python.
- api:run_command: can now use ``raw`` connections (no need for python at the dest)
- api: introduce `bg_start`, `bg_stop` that generates the command for
  starting/stopping backgroung process on the remote nodes.
  see also below
- api: introduce `background` keyword. It serves the same purpose of
  `bg_start/end` but is more generic in the sense that many modules can benefit
  from the keyword and it doesn't have any dependencies. Under the hood this will
  generate an async Ansible tasks with infinite timeout.
- api:``populate_keys``: make sure the public key is added only once to the remote `authorized_keys`
- svc/dstat: make it a context manager, adapt the examples
- svc/tcpdump: make it a context manager, adapt the examples
- svc/locust: update to the latest version. align the API to support
  parameter-less ``deploy`` method (run ``headless`` by default)
- Doc: they-use-it updated
- g5k: NetworkConf doesn't need an id anymore.
    The ``id`` is still mandatory when using a dictionnary to build the whole configuration.



.. _v6.2.0:

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


.. _v6.1.0:

6.1.0
-----

Breaking:

- svc/netem-htb: Rework on the various service APIs. Now the user can use
  a builder pattern to construct its network topology with Netem and
  NetemHTB.  Check the examples to see how it looks like. Unfortunately
  this breaks the existing APIs.

Misc:

- provider: Openstack provider fixed
- api: add ``run_once`` and ``delegate_to`` keywords
- api: add ``populate_keys`` that populate ssh keys on all hosts (use case:
  MPI applications that needs to all hosts to be ssh reachable)
- tasks: env implements ``__contains__`` (resp. ``setdefault``) to check if a
  key is in the env (resp. set a default value) (cherry-pick from 5.x)
- svc/monitoring: remove the use of explicit ``become`` in the deployment


.. _v6.0.4:

6.0.4
-----

- svc/docker: allow to specify a port (cherry-pick from 5.x)
- doc: fix typo  + some improvements (emojis)
- api/play_on: now accepts an Ansible Inventory (cherry-pick from 5.x)


.. _v6.0.3:

6.0.3
-----

- svc:netem: fix an issue with missing self.extra_vars
- svc:monitoring: stick to influxdb < 2 for now (influxdb2 requires an auth)


.. _v6.0.2:

6.0.2
-----

- doc/G5k: Add an example that makes use of the internal docker registries
  of Grid'5000


.. _v6.0.1:

6.0.1
-----

- doc: install instructions on the front page
- doc/G5k: Document G5kTunnel


.. _v6.0.0:

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


Older versions
---------------

.. _v5.5.4:

5.5.4
+++++

- tasks: env implements ``__contains__`` (resp. ``setdefault``) to check if a
  key is in the env (resp. set a default value)


.. _v5.5.3:

5.5.3
+++++

- api: ``play_on`` can be called with an inventory file



.. _v5.5.2:

5.5.2
+++++

- svc/docker: allow to specify a port


.. _v5.5.1:

5.5.1
+++++

- G5k: support for ``exotic`` job type. If you want to reserve a node on
  exotic hardware, you can pass either ``job_type=[allow_classic_ssh, exotic]``
  or ``job_type=[deploy, exotic]``. Passing a single string to ``job_type`` is
  also possible (backward compatibility)


.. _v5.5.0:

5.5.0
+++++

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


.. _v5.4.3:

5.4.3
+++++

- G5k: returned Host.address was wrong when using vlans
- Doc: fix execo url


.. _v5.4.2:

5.4.2
+++++

- Doc: G5k change tutorial URL
- G5k: Align the code with the new REST API for vlans (need python-grid5000 >= 1.0.0)


.. _v5.4.1:

5.4.1
+++++

- Service/docker: swarm support


.. _v5.4.0:

5.4.0
+++++

- Support ``from enoslib import *``
- G5k: surgery in the provider: dictectomy.
    - extra: allow job inspection through ``provider.hosts`` and ``provider.networks``
- G5k: reservation at the server level is now possible
    Use case: you need a specific machine (or certain number of machines over a specific set of machines)
- G5k: configuration can take the project as a key
- Doc: G5k uniformize examples


.. _v5.3.4:

5.3.4
+++++

- G5k: make the project configurable (use the project key in the
  configuration)


.. _v5.3.3:

5.3.3
+++++

- G5k: fix an issue when dealing with global vlans


.. _v5.3.2:

5.3.2
+++++

- VMonG5k: resurrect nested kvm


.. _v5.3.1:

5.3.1
+++++

- Doc: Add E2Clab


.. _v5.3.0:

5.3.0
+++++

- Service/dstat: migrate to ``dool`` as a ``dstat`` alternative
- Fix Ansible 2.9.11 compatibility


.. _v5.2.0:

5.2.0
+++++

- Api: Add ``get_hosts(roles, pattern_hosts="all")`` to retrieve a list of host matching a pattern
- Doc: Fix netem example inclusion



.. _v5.1.3:

5.1.3
+++++

- Tasks: Fix an issue with predefined env creation
- Service/dstat: Fix idempotency of deploy


.. _v5.1.2:

5.1.2
+++++

- Tasks: automatic ``env_name`` change to remove colons from the name


.. _v5.1.1:

5.1.1
+++++

- Netem: Better support for large deployment (introduce `chunk_size` parameter)


.. _v5.1.0:

5.1.0
+++++

- Tasks:
    - review the internal of the implementation
    - support for nested tasks added
- Doc:
    - Add autodoc summary in the APIs pages (provided by autodocsumm)
    - Align some examples with the new Netem implementation


.. _v5.0.0:

5.0.0
+++++

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


.. _v4.11.0:

4.11.0
++++++

- Service/docker:
    - Allow to mount the whole docker dir elsewhere
      (e.g in /tmp/docker instead of /var/lib/docker)
    - Default to registry:None, meaning that this will
      deploy independent docker daemons


.. _v4.10.1:

4.10.1
++++++

- Service/dstat: doc
- service/monitoring: typecheck



.. _v4.10.0:

4.10.0
++++++

- Service/dstat: add a new dstat monitoring
- Doc: some fixes (comply with the discover_networks)


.. _v4.9.4:

4.9.4
+++++

- Doc: some fixes


.. _v4.9.3:

4.9.3
+++++

- Doc: some fixes / add a ref


.. _v4.9.2:

4.9.2
+++++

- Doc: add some refs in they-use-it.rst


.. _v4.9.1:

4.9.1
+++++

- Fix: include the missing BREAKING change of 4.9.0


.. _v4.9.0:

4.9.0
++++++

- Doc: Add a ref
- Service/locust: Fix density option
- Service/Netem: support for bridged networks
- Api/BREAKING: `discover_networks` doesn't have side effects anymore on the hosts.


.. _v4.8.12:

4.8.12
++++++

- Doc: Simplify network emulation example


.. _v4.8.11:

4.8.11
++++++

- VMonG5K: Don't fail if #pms > #vms
- Doc: add madeus-openstack-benchmarks
- Service/locust: review, add a density option that controls
  the number of slave to start on each node.
- Doc: Expose the Locust documentation


.. _v4.8.10:

4.8.10
++++++

- Service/monitoring: allow for some customisations
- VMonG5K: use the libvirt directory for all the operations


.. _v4.8.9:

4.8.9
+++++

- Service/netem: fix validate when network is partitioned


.. _v4.8.8:

4.8.8
+++++

- Doc: Add content for quick access
- Doc: Add parameters sweeper tutorial


.. _v4.8.7:

4.8.7
+++++

- Doc: clean and use continuation line
- Service/docker: remove useless statement


.. _v4.8.6:

4.8.6
+++++

- Api/play_on: don't gather facts twice
- VMonG5k: 🐎 enable virtio for network device 🐎
- Service/monitoring: add the influxdb datasource automatically


.. _v4.8.5:

4.8.5
+++++

- Api: Introduce ``ensure_python[2,3]`` to make sure python[2,3]
  is there and make it the default version (optionally)
- Api: ``wait_ssh`` now uses the raw module
- Api: rename some prior with a double underscore (e.g. ``__python3__``)


.. _v4.8.4:

4.8.4
+++++

- Doc: Handling of G5k custom images
- Host: Implementation of the __hash__() function
- API: ``play_on`` offers new strategies to gather Ansible facts
- type: Type definitions for Host, Role and Network


.. _v4.8.3:

4.8.3
+++++

- G5K/api: job_reload_from_name fix for anonymous user
- Doc: some cleaning, advertise mattermost channel


.. _v4.8.2:

4.8.2
+++++

- VMonG5K: some cleaning
- Host: copy the passed extra dict
- Skydive: fix docstring


.. _v4.8.1:

4.8.1
+++++

- Service/Monitoring: fix collector_address for telegraf agents


.. _v4.8.0:

4.8.0
+++++

- Enforce python3.6+ everywhere
- Add more functionnal tests
- Api: ``play_on`` accepts a ``priors`` parameters
- Add ``run`` command for simplicity sake
- ``enoslib.host.Host`` is now a dataclass
- Typecheck enabled in CI


.. _v4.7.0:

4.7.0
+++++

- G5k: Default to Debian10
- Vagrant: Defaut to Debian10
- VMonG5k:
    - Default to Debian10
    - Activate VLC console (fix an issue with newest G5K virt images...)
    - Run VMs as root


.. _v4.6.0:

4.6.0
+++++

- Chameleon: minor fixes, support for the primer example
- Vagrant: customized name and config is now supported
- Locust/service: initial version (locust.io)
- G5k: support for arbitrary SSH key


.. _v4.5.0:

4.5.0
+++++

- Dependencies: upgrade python-grid5000 to 0.1.0+
- VMonG5K/API break: use g5k api username instead of USER environment variable
- VMonG5K: make the provider idempotent


.. _v4.4.5:

4.4.5
+++++

- Doc: some fixes
- VMonG5k: change gateway description


.. _v4.4.4:

4.4.4
+++++

- Doc: distem makes use of stretch image by default


.. _v4.4.3:

4.4.3
+++++

- Doc: Doc updates (readme and distem)


.. _v4.4.2:

4.4.2
+++++

- Doc: update distem tutorial


.. _v4.4.1:

4.4.1
+++++

- Catch up changelog


.. _v4.4.0:

4.4.0
+++++

- New provider: Distem


.. _v4.3.1:

4.3.1
+++++

- G5k: fix walltime > 24h


.. _v4.3.0:

4.3.0
+++++

- G5k: ``get_api_username`` to retrieve the current user login
- Doc: fix ``play_on``


.. _v4.2.5:

4.2.5
+++++

- Services: Add missing files in the wheel


.. _v4.2.4:

4.2.4
+++++

- Skydive: Fix topology discovery
- Doc: Fix ``pattern_hosts`` kwargs


.. _v4.2.3:

4.2.3
+++++

- Doc: Factorize readme and doc index


.. _v4.2.2:

4.2.2
+++++

- Doc: Fix sphinx warnings


.. _v4.2.1:

4.2.1
+++++

- Fix changelog syntax


.. _v4.2.0:

4.2.0
+++++

- Service: Add skydive service
- Service: Internal refactoring


.. _v4.1.1:

4.1.1
+++++

- Catch-up changelog for 4.1.x



.. _v4.1.0:

4.1.0
+++++

- API(breaks): Introduce ``patterns_hosts`` as a keyword argument
- API: Introduce ``gather_facts`` function
- Doc: Fix python3 for virtualenv on g5k
- API: Allow top level and module level arguments to be passed
  in ``run_command`` and ``play_on``
- G5K: Use ring to cache API requests results
- API: Support for ``raw`` module in ``play_on``
- Black formatting is enforced


.. _v4.0.3:

4.0.3
+++++

- Doc: Fix netem service link


.. _v4.0.2:

4.0.2
+++++

- Doc: Add a placement example (vmong5k)


.. _v4.0.1:

4.0.1
+++++

- Doc: Capitalize -> EnOSlib


.. _v4.0.0:

4.0.0
+++++

- Service: add Netem service as a replacement for ``(emulate|reset|validate)_network`` functions.
  Those functions have been dropped
- Service: add Docker service. Install the docker agent on all your nodes and
  optionally a docker registry cache
- Upgrade jsonschema dependency
- Migrate sonarqube server
- Vagrant: OneOf for ``flavour`` and ``flavour_desc`` has been fixed
- Api: ``play_on`` tasks now accept a ``display_name`` keyword. The string will
  be displayed on the screen as the name of the command.


.. _v3.4.2:

3.4.2
+++++

- Service: fix example


.. _v3.4.1:

3.4.1
+++++

- Service: monitoring update doc


.. _v3.4.0:

3.4.0
+++++

- Introduce a monitoring service (quickly deploy a monitoring stack)
- API: Add `display_name` kwargs in `play_on` (debug/display purpose)


.. _v3.3.3:

3.3.3
++++++

- Doc: in using-tasks include whole python script


.. _v3.3.2:

3.3.2
++++++

- Doc: fix using-tasks output


.. _v3.3.1:

3.3.1
++++++

- Doc: Include changelog in the documentation
- ChameleonBaremetal: fix tutorial


.. _v3.3.0:

3.3.0
++++++

- G5k: automatic redepoy (max 3) when nodes aren't deployed correctly


.. _v3.2.4:

3.2.4
++++++

- Avoid job_name collision from 2 distinct users


.. _v3.2.3:

3.2.3
++++++

- Fix an issue with emulate_network (it now uses `inventory_hostname`)


.. _v3.2.2:

3.2.2
++++++

- VMonG5k: fix the networks returned value


.. _v3.2.1:


3.2.1
++++++

- G5k: Fix static driver


.. _v3.2.0:

3.2.0
++++++

- VMonG5K: Enables taktuk for image broadcast


.. _v3.1.4:

3.1.4
++++++

- Doc: Fix network_emulation conf


.. _v3.1.3:

3.1.3
++++++

- Doc: add missing files


.. _v3.1.2:

3.1.2
++++++

- Doc: Document network emulation


.. _v3.1.1:

3.1.1
++++++

- Doc: VMonG5K warning about the `working_dir` being removed


.. _v3.1.0:

3.1.0
++++++

- VMonG5k: expose `start_virtualmachines` function


.. _v3.0.1:

3.0.1
++++++

- Doc: Add VMonG5k primer
- Doc: Secure credential file


.. _v3.0.0:

3.0.0
++++++

- [G5k]: now uses python-grid5000 for all the interactions with Grid'5000
- [VMonG5K]: Add a gateway option
- [VMonG5K]: Coerce to `enoslib.Host` before returning from init.


.. _v2.2.10:

2.2.10
++++++

- Doc: use std env for primer on g5k


.. _v2.2.9:

2.2.9
++++++

- Doc add 10.1109/TPDS.2019.2907950


.. _v2.2.8:

2.2.8
++++++

- Dependencies: add pyyaml and be a bit strict
- tasks: add the knowledge of host datastructure when deserializing
- Vagrant: force gateway ip to string
- Doc: add performance tuning section


.. _v2.2.7:

2.2.7
++++++

- Doc: Gender equality fix


.. _v2.2.6:

2.2.6
++++++

- Doc: static provider
- Doc: various fixes


.. _v2.2.5:

2.2.5
++++++

- CI: add `play_on` functional test


.. _v2.2.4:

2.2.4
++++++

- Doc: Update Primer (add g5k example)


.. _v2.2.3:

2.2.3
++++++

- API: fix `gather_facts=False` in `play_on`


.. _v2.2.2:

2.2.2
++++++

- Doc: put project boostrap at the end (formerly quickstart)


.. _v2.2.1:

2.2.1
++++++

- Doc: add EnOSlib primer
- API: discover_network now add `<network>_ip` and `<network>_dev` in the hosvars


.. _v2.2.0:

2.2.0
++++++

- API: Introduce `play_on` context_manager to describe a playbook directly from python


.. _v2.1.0:

2.1.0
++++++

- API: In memory inventory. Generating a inventory file is not mandatory anymore.
       On can pass the provider roles in most of the API calls.
- VMonG5K: allow to specify a working directory
- Dependencies: Upgrade Ansible to latest stable (2.7.x)


.. _v2.0.2:

2.0.2
++++++

- (breaking) VMonG5K/Vagrant: Unify code. `flavour_desc` dict can be used after
  building the MachineConfiguration.


.. _v2.0.1:

2.0.1
++++++

- VMonG5K: Package was missing site.yml file


.. _v2.0.0:

2.0.0
++++++

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


.. _v1.12.3:

1.12.3
++++++

- API: `utils.yml` playbook now forces fact gahering.
- Misc: initial gitlab-ci supports


.. _v1.12.2:

1.12.2
++++++

- G5K: Refix an issue when number of nodes is zero


.. _v1.12.1:

1.12.1
++++++

- G5K: fix an issue when number of nodes is zero


.. _v1.12.0:

1.12.0
++++++

- API: `emulate|reset|validate` now accept an extra_vars dict
- G5K: `secondary_networks` are now a mandatory key
- G5K: support for zero nodes roles


.. _v1.11.2:

1.11.2
++++++

- Make sure role and roles are mutually exclusive


.. _v1.11.1:

1.11.1
++++++

- Fix empty `config_file` case in enostask


.. _v1.11.0:

1.11.0
++++++

- G5K: add static oar job support


.. _v1.10.0:

1.10.0
++++++

- G5K: align the subnet description with the other network
- API: validate_network now filters devices without ip address
- API: check_network now uses JSON serialisation to perform better


.. _v1.9.0:

1.9.0
++++++

- G5K api: expose get_clusters_sites
- G5K: dhcp is blocking
- G5k: introduce drivers to interact with the platform


.. _v1.8.2:

1.8.2
++++++

- Chameleon: fix flavor encoding
- Chameleon: Create one reservation per flavor
- Openstack: fix python3 compatibility


.. _v1.8.1:

1.8.1
++++++

- relax openstack client constraints


.. _v1.8.0:

1.8.0
++++++

- G5K api: expose exec_command_on_nodes
- Openstack: enable the use of session for blazar
- Openstack: Allow keystone v3 authentification


.. _v1.7.0:

1.7.0
++++++

- G5K api: fixed get_clusters_interfaces function
- Ansible: group vars were'nt loaded
- Allow fake interfaces to be mapped to net roles


.. _v1.6.0:

1.6.0
++++++

- G5K: add subnet support
- An enostask can now returns a value
- Openstack/Chameleon: support region name
- Openstack/Chameleon: support for extra prefix for the resources
- Chameleon: use config lease name


.. _v1.5.0:

1.5.0
++++++

- python3 compatibility
- Confirm with predictable NIC names on g5k


.. _v1.4.0:

1.4.0
++++++

- Fix the autodoc generation
- Document the cookiecutter generation
- Default to debian9 for g5k


.. _v1.3.0:

1.3.0
++++++

- Change setup format
- Move chameleon dependencies to extra_require


.. _v1.2.1:

1.2.1
++++++

- Drop validation of the bandwitdh
- Add missing host file


.. _v1.2.0:

1.2.0
++++++

- Add reset network


.. _v0.0.6:

0.0.6
++++++

- add `min` keyword in machine descipriotn on for G5K


.. _v0.0.5:

0.0.5
++++++

- reservation is supported in g5k provider
- `expand_groups` is available in the api
- `get_cluster_interfaces` is available in the g5k api.


.. _v0.0.4:

0.0.4
++++++

- Exclude not involved machines from the tc.yml run
- Take force_deploy in g5k provider
- Wait ssh to be ready when `check_network=True` in `generate_inventory`
- Add start/end enostask logging


.. _v0.0.3:

0.0.3
++++++

- Add static provider
- Add OpenStack provider (and chameleon derivatives)
- Add `provider_conf` validation
- Rearchitect providers
- Add dummy functionnal tests
- Add network emulation


.. _v0.0.2:

0.0.2
++++++

- Add fake interface creation option un check_network
- Encapsulate check_network in generate_inventory
- Add automatic discovery of network interfaces names/roles
- Add vagrant/g5k provider


.. _v0.0.1:

0.0.1
++++++

- Initial version
