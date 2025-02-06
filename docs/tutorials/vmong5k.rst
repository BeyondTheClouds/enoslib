.. _vmong5k:

*****************
VMonG5K tutorials
*****************

.. contents::
   :depth: 2

This tutorial leverages the :py:class:`~enoslib.infra.enos_vmong5k.provider.VMonG5k` provider: a provider that provisions
virtual machines for you on Grid'5000.


.. hint::

   For a complete schema reference see :ref:`vmong5k-schema`

.. include:: ./setup_g5k.rst


Basic example
=============

We'll imagine a system that requires 5 compute machines and 1 controller machine.
We express this using the :py:class:`~enoslib.infra.enos_vmong5k.provider.VMonG5k` provider:

.. literalinclude:: vmong5k/tuto_vmong5k.py
   :language: python
   :linenos:

:download:`tuto_vmong5k.py <vmong5k/tuto_vmong5k.py>`

- You can launch the script using :

.. code-block:: bash

    $ python tuto_vmg5k.py

- The raw data structures of EnOSlib will be displayed and you should be able to
  connect to any machine using SSH and the root account.


How it works
============

* The :py:class:`~enoslib.infra.enos_vmong5k.provider.VMonG5k` provider
  internally uses the :py:class:`~enoslib.infra.enos_g5k.provider.G5k`
  provider.  In particular it uses the default job type to obtain physical
  nodes with a standard Grid'5000 environment, and it also claims an extra
  ``slash_22`` subnet.

* SSH access will be granted to the VMs using the ``~/.ssh/id_rsa | ~/.ssh/id_rsa.pub`` keypair.
  So these files must be present in your home directory.

* The :ref:`working_dir <vmong5k-schema>` setting controls where the
  temporary files and virtual images disks will be stored. The default is
  to store everything in the temp folder of the physical nodes.

* You might be interested in adding :py:func:`~enoslib.api.wait_for` just
  after :py:meth:`~enoslib.infra.enos_vmong5k.provider.VMonG5k.init`
  to make sure SSH is up and running on all VMs. Otherwise you might get an
  *unreachable* error from SSH.

* The provider will try to use as few physical hosts per group of machines
  as possible, using a very simple bin-packing allocation algorithm. Note
  however that each requested group of machines will always use its own
  physical hosts. For instance, if you create 2 groups with 1 VM each, it
  will use 2 physical hosts.

* By default, the provider will allocate VMs on physical hosts based on
  the number of hardware CPU threads.  It is possible to use the number of
  hardware CPU cores instead: this will allocate fewer VMs per physical
  host, but you will likely obtain better CPU performance in the VMs.
  This is controlled by the :ref:`vcore_type <vmong5k-schema>` parameter.

.. warning::

   The :ref:`working_dir <vmong5k-schema>` and all its content is deleted
   by the provider when calling
   :py:meth:`~enoslib.infra.enos_vmong5k.provider.VMonG5k.destroy`.


Changing resource size of virtual machines
==========================================

As for the CPU and memory resources, you can simply change the name of the
flavour (available flavours are listed `here
<https://gitlab.inria.fr/discovery/enoslib/-/blob/master/enoslib/infra/enos_vmong5k/constants.py#L20-27>`_),
or create your own flavour with ``flavour_desc``.

.. code-block:: python

    [...]
    .add_machine(
        [...],
        flavour_desc={"core": 1, "mem": "512"}
    )

Customizing the disks of Virtual Machines
=========================================

- **Adding a new disk:**
  Using the disk attribute of `flavour_desc` will create a new disk and make it
  available to the VM. For instance to get an extra disk of 10GB you can use
  this python configuration parameter:

  .. code-block:: python

    [...]
    .add_machine(
        [...],
        flavour_desc={"core": 1, "mem": 512, "disk": 10}
    )

Note that with the above configuration an extra disk of 10GB will be provisioned and
available to the Virtual Machine. In the current implementation, the disk is neither formatted nor mounted in the Virtual Machine OS.

- **Make an external (not managed by EnOSlib) disk available to the Virtual Machine**
  A typical use case is to use an hardware disk from the host machine.
  In this situation, use the `extra_devices` parameter of the configuration.
  It corresponds to the XML string of `Libvirt <https://libvirt.org/formatdomain.html#hard-drives-floppy-disks-cdroms>`_.

  .. code-block:: python

    [...]
    .add_machine(
        [...],
        extra_devices = """
        <disk type='block' device='disk'>
        <driver name='qemu' type='raw'/>
        <source dev='/dev/disk/by-path/pci-0000:82:00.0-sas-phy1-lun-0'/>
        <target dev='vde' bus='virtio'/>
        </disk>
        """

- **Resize the root filesystem**
  To do so, you will need to get the *qcow2* file, put it in your public folder, and
  resize it. Location of the file is shown `here <https://gitlab.inria.fr/discovery/enoslib/-/blob/master/enoslib/infra/enos_vmong5k/constants.py#L10>`_.

  .. code-block:: bash

    cp /grid5000/virt-images/debian10-x64-nfs.qcow2 $HOME/public/original.qcow2
    cd $HOME/public
    qemu-img info original.qcow2  # check the size (should be 10GB)
    qemu-img resize original.qcow2 +30G
    # at this stage, image is resized at 40GB but not the partition
    virt-resize --expand /dev/sda1 original.qcow2 my-image.qcow2
    rm original.qcow2
    # now you can check the size of each partition (/dev/sda1 should be almost 40GB)
    virt-filesystems –long -h –all -a my-image.qcow2

  Finally, you need to tell EnosLib to use this file with:


  .. code-block:: python

    Configuration.from_settings(...
                                image="/home/<username>/public/my-image.qcow2",
                                ...
                                )


Large-scale VM deployments
==========================

When deploying a large number of VMs, you should follow the guide at
:ref:`performance_tuning` to make it work and ensure it is reasonably
efficient.  Enoslib is able to deploy and manage 3000 VMs in a relatively
short amount of time.

.. literalinclude:: ./performance_tuning/vmong5k_forks.py
   :language: python
   :linenos:

:download:`vmong5k_forks.py <performance_tuning/vmong5k_forks.py>`


Controlling the virtual machines placement
==========================================

There are a few ways to control VM placement:

- each group is considered independently. It means that you can separate
  VMs on different physical hosts by just declaring them in different
  groups.  They can still share the same roles.

- you can use :ref:`vcore_type <vmong5k-schema>` to control whether VMs
  will be allocated based on the physical number of cores or physical
  number of hyper-threads.

.. literalinclude:: ./vmong5k/tuto_placement_basic.py
   :language: python
   :linenos:

:download:`tuto_placement_basic.py <vmong5k/tuto_placement_basic.py>`


Controlling the virtual machines placement (advanced)
=====================================================

If you need more control, you will have to reserve the physical resources
yourself and then pass them to the VMonG5K provider:

.. literalinclude:: ./vmong5k/tuto_placement.py
   :language: python
   :linenos:

:download:`tuto_placement.py <vmong5k/tuto_placement.py>`


Multisite Support
=================

You can specify clusters from different sites in the configuration. The provider
will take care of reserving nodes and subnet on the different sites and
configure the VMs' network card accordingly.


.. _vmong5k_home_directory:
Mounting your home directory (or a group storage)
=================================================

Mounting your home directory within the VMs is a two steps process.  It first
relies on a white list of IPS allowed to mount the NFS exported home: so you need
to add your VM's IPS to this list. This is done using an REST API call.
Second, you need to mount the home inside your VMs.


.. literalinclude:: ./vmong5k/tuto_vmong5k_home.py
   :language: python
   :linenos:

:download:`tuto_vmong5k_home.py <vmong5k/tuto_vmong5k_home.py>`

Note that you can allow any group storage using :py:func:`~enoslib.infra.enos_g5k.g5k_api_utils.enable_group_storage`
