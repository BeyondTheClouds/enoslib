******************
Provider::Vagrant
******************

.. contents::
   :depth: 2

This tutorial will let you get started using |enoslib| and vagrant. This will
present you the bare minimum to start some machines and distribute them into
the desired roles.

.. hint::

   For a complete schema reference see :ref:`vagrant-schema`

Installation
------------

.. code-block:: bash

    $ pip install enoslib[vagrant]

.. note::

  It's a good practice to use a virtualenv or a python version manager like
  `pyenv`_.

.. note::

   The default backend used is libvirt, so you'll also need to have the
   appropriate vagrant-libvirt plugin.  Nowadays, it is shipped within a
   container image (alongside the vagrant program). See
   https://vagrant-libvirt.github.io/vagrant-libvirt/installation.html#docker--podman

Using the API
-------------

From a dictionary
******************

The following ``tuto_vagrant.py`` implements the desired workflow.

.. literalinclude:: vagrant/tuto_vagrant.py
   :language: python
   :linenos:

- The configuration is specified and passed to the provider.
  Here we want two machines. Each machine will be given some
  roles (``control`` and/or ``compute``). These two nodes will
  have one network card configured using the same network whose
  role is ``n1``.

    .. note::

        Machine roles and network roles are transparent to the |enoslib|. The
        semantic is left to the application using it.

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_vagrant.py

- Additionally, there are two keys to personalize the vagrant configuration:

  1. The key ``config_extra`` enables customized expressions of the ``config``
     variable in a Vagrant description. For example, in order to add a
     synchronised folder in the virtual machine the key may be set as follows:

     .. code-block:: yaml

        config_extra: |
          config.vm.synced_folder ".",
                                   "/vagrant",
                                   owner: "vagrant",
                                   group: "vagrant"
  2. The key ``name_prefix`` changes the default prefix of virtual machines'
     names. This key can be set as a global attribute at the root level or it
     can be set at group level along side the description fo a ``machine``. For
     example, the following combination is possible:

     .. code-block:: yaml

        backend: libvirt
        box: generic/ubuntu1804
        name_prefix: vm

        resources:
          machines:
            - roles: [CloudOne]
              name_prefix: CloudOne
            - roles: [CloudTwo]
              flavour: large
              number: 1


     .. note::

        When ``name_prefix`` is set and there is only one machine in the group
        (default behaviour) any counter is append to the name of the machine.

Programmatic way
****************


.. literalinclude:: vagrant/tuto_vagrant_p.py
   :language: python
   :linenos:

.. _pyenv: https://github.com/pyenv/pyenv
