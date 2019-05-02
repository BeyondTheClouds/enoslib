.. _vmong5k:

Provider::VMonG5K
=================

This tutorial leverages the ``VmonG5k`` provider: a provider that provisions
virtual machines for you on Grid'5000. 


.. hint::

   For a complete schema reference see :ref:`vmong5k-schema`

.. include:: ./setup_g5k.rst


To accesss your virtual machines from your local machine, see below.


Basic example
-------------

We'll imagine a system that requires 100 compute machines and 3 controller machines.
We express this using the ~VmonG5K~ provider:

.. literalinclude:: vmong5k/tuto_vmong5k.py
   :language: python
   :linenos:


- You can launch the script using :

    .. code-block:: bash

        $ python tuto_vmg5k.py

- The raw data structures of EnOSlib will be displayed and you should be able to
  connect to any machine using SSH and the root account.

Notes
-----

* The ``VmonG5K`` provider internally uses the ``G5k`` provider. In particular
  it sets the ``job_type`` to ``allow_classic_ssh`` and claim an extra
  ``slash_22`` subnet.

* SSH access will be granted to the VMs using the ``~/.ssh/id_rsa | ~/.ssh/id_rsa.pub`` keypair.
  So these files must be present in your home directory.

* The ``working_dir`` setting controls where the temporary files and virtual
  images disks will be stored. The default is to store everything in the temp
  folder of the physical nodes.


.. warning::

   The ``working_dir`` and all its content is deleted by the provider.



|enoslib| primer using VMonG5k
------------------------------

.. literalinclude:: ansible-integration/flent_on_vmong5k.py
   :language: python
   :linenos:


SSH external access to the virtual machines
-------------------------------------------

This is mandatory if you deployed from your local machine.

- Solution 1: use the `Grid'5000 VPN <https://www.grid5000.fr/w/VPN>`_
- Solution 2: Add the following in your configuration force Ansible to
  jump through a gateway:

::

   Configuration.from_settings(...
                               gateway=access.grid5000.fr,
                               gateway_user=<g5k_login>
                              )
