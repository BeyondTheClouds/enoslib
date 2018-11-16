Tutorial 6 - Working with virtual machines on Grid'5000
=======================================================

This tutorial leverages the ``VmonG5k`` provider: a provider that provisions
virtual machines for you on Grid'5000. 

Installation
------------


On Grid'5000, you can go with a virtualenv :

.. code-block:: bash

    $ virtualenv venv
    $ source venv/bin/activate
    $ pip install -U pip

    $ pip install enoslib

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
  So these files should be present in your home directory.
