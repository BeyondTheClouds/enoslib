.. _installation:

Tutorial 1 - Working with Vagrant
=================================

This tutorial will let you get started using |enoslib| and vagrant. This will
present you the bare minimum to start some machines and distribute them into
the desired roles.

Installation
------------

.. code-block:: bash

    $ pip install enoslib

.. note::

  It's a good practice to use a virtualenv or a python version manager like
  `pyenv`_.

Using the API
-------------

The following ``tuto_vagrant.py`` implements the desired workflow.

.. literalinclude:: vagrant/tuto_vagrant.py
   :language: python
   :linenos:

- Lines 5-18 describe the wanted resources. Here we want two machines. Each
  machine will be given some roles (``control`` and/or ``compute``). These two
  nodes will have one network card configured using the same network whose role
  is ``n1``.

    .. note::

        Machine roles and network roles are transparent to the |enoslib|. The
        semantic is left to the application using it.

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_vagrant.py


- The content of the generated inventory should look like the following:

    .. literalinclude:: vagrant/hosts
     :language: python


    .. note::

        Note the extra variables concerning the network. They can be use in
        your ansible playbooks to refer to a specific network.

.. _pyenv: https://github.com/pyenv/pyenv
