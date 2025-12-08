****************
FABRIC tutorials
****************

.. contents::
   :depth: 2

This tutorial will let you get started using |enoslib| and FABRIC. This will
present you the bare minimum to start some machines and distribute them into
the desired roles.

.. hint::

   For a complete schema reference see :ref:`fabric-schema`

Installation
------------

.. code-block:: bash

    $ pip install enoslib[fabric]

.. note::

  It's a good practice to use a virtualenv or a python version manager like
  `pyenv`_.

Using the API
-------------

From a dictionary
*****************

The following ``tuto_fabric.py`` implements the desired workflow.

.. literalinclude:: fabric/tuto_fabric.py
   :language: python
   :linenos:

- The configuration is specified and passed to the provider.
  Here we want two machines. Each machine will be given some
  roles (``CloudOne`` and/or ``CloudTwo``). These two nodes will
  have FABNET IPv4 configured whose role is ``n1``.

    .. note::

        Machine roles and network roles are transparent to the |enoslib|. The
        semantic is left to the application using it.

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_fabric.py

Complex Example
***************

The following ``tuto_fabric_complex.py`` in a more complex example that shows how to provision
GPUs and storage.

.. literalinclude:: fabric/tuto_fabric_complex.py
   :language: python
   :linenos:


 - The key ``gpus`` enables adding GPU to the provisioned nodes. For example, in order to add a
   GPU the key may be set as follows:

    .. code-block:: yaml

        gpus:
         - model: Tesla T4


  - The key ``storage`` enables adding NVME, and/or NAS storage. For example, in order to add a
    NVMe and NAS storage the key may be set as follows:

    .. code-block:: yaml

        storage:
         - kind: NVME
           model: P4510
           name: nvme-1
           mount_point: /mnt/nvme
         - kind: Storage
           model: NAS
           name: pre-requested-storage-name

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_fabric_complex.py

    .. note::

         What GPUs and storage devices are available would vary site to site.

    .. note::

        Provisioning GPUs and storage requires to request privileges on FABRIC. You can do that by
        creating a ticket on the FABRIC portal.


.. _pyenv: https://github.com/pyenv/pyenv
