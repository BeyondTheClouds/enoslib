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


To accesss your virtual machines from your local machine, see below.


Basic example
=============

We'll imagine a system that requires 5 compute machines and 1 controller machine.
We express this using the :py:class:`~enoslib.infra.enos_vmong5k.provider.VMonG5k` provider:

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

* The :py:class:`~enoslib.infra.enos_vmong5k.provider.VMonG5k` provider
  internally uses the :py:class:`~enoslib.infra.enos_g5k.provider.G5k`
  provider.  In particular it uses the default job type to obtain physical
  nodes with a standard Grid'5000 environment, and it also claims an extra
  ``slash_22`` subnet.

* SSH access will be granted to the VMs using the ``~/.ssh/id_rsa | ~/.ssh/id_rsa.pub`` keypair.
  So these files must be present in your home directory.

* The ``working_dir`` setting controls where the temporary files and virtual
  images disks will be stored. The default is to store everything in the temp
  folder of the physical nodes.

* You might be interested in adding :py:func:`~enoslib.api.wait_for` just
  after :py:meth:`~enoslib.infra.enos_vmong5k.provider.VMonG5k.init`
  to make sure SSH is up and running on all VMs. Otherwise you might get an
  *unreachable* error from SSH.

* The provider will try to use as few physical hosts per group of machines as
  possible. Note that you'll anyway get at least as many physical machines as group.

.. warning::

   The ``working_dir`` and all its content is deleted by the provider when
   calling :py:meth:`~enoslib.infra.enos_vmong5k.provider.VMonG5k.destroy`.


Changing resource size of virtual machines
==========================================

As for the CPU and memory resources, you can simply change the name of the
flavour (available flavours are listed `here <https://gitlab.inria.fr/discovery\
/enoslib/-/blob/master/enoslib/infra/enos_vmong5k/constants.py#L17-24>`_), or
create your own flavour with ``flavour_desc``.

.. code-block:: python

    [...]
    .add_machine(
        [...],
        flavour_desc={"core": 1, "mem": "512"}
    )

Notes on the disks of Virtual Machines
--------------------------------------

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

|enoslib| primer using VMonG5k
==============================

.. literalinclude:: ansible-integration/flent_on_vmong5k.py
   :language: python
   :linenos:


SSH external access to the virtual machines
===========================================

This is mandatory if you deployed from your local machine.

- Solution 1: use the `Grid'5000 VPN <https://www.grid5000.fr/w/VPN>`_
- Solution 2: Add the following in your configuration force Ansible to
  jump through a gateway (``access.grid5000.fr``):

  .. code-block:: python

    Configuration.from_settings(...
                                gateway=True
                                ...
                               )

Controlling the virtual machines placement
==========================================


.. literalinclude:: ./vmong5k/tuto_placement.py
   :language: python
   :linenos:


Multisite Support
=================

You can specify clusters from different sites in the configuration. The provider
will take care of reserving nodes and subnet on the different sites and
configure the VMs' network card accordingly.


Mounting your home directory (or a group storage)
=================================================

Mounting your home directory within the VMs is a two steps process.  It first
relies on a white list of IPS allowed to mount the NFS exported home: so you need
to add your VM's IPS to this list. This is done using an REST API call.
Second, you need to mount the home inside your VMs.


.. literalinclude:: ./vmong5k/tuto_vmong5k_home.py
   :language: python
   :linenos:


Note that you can allow any group storage using :py:func:`~enoslib.infra.enos_g5k.g5k_api_utils.enable_group_storage`
