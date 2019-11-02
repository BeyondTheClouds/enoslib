.. _distem:

****************
Provider::Distem
****************

.. contents::
   :depth: 2

This tutorial leverages the ``Distem`` provider: a provider that creates
containers for you on Grid'5000.

.. note::

    More details on : http://distem.gforge.inria.fr/


.. hint::

   For a complete schema reference see :ref:`distem-schema`

.. include:: ./setup_g5k.rst


Basic example
=============

We'll imagine a system that requires 50 compute machines and 1 controller machines.
We express this using the Distem provider:

.. hint::

   - If you don't have any image :

   - $) wget 'http://public.nancy.grid5000.fr/~msimonin/public/distem-stretch.tar.gz' -P /home/public

.. literalinclude:: distem/tuto_distem.py
   :language: python
   :linenos:

.. note::
    - You can customize your virtual environment as explained in :
      http://distem.gforge.inria.fr/faq.html#how-to-customize-your-virtual-environment
    - Alternatively a quick way to create a base virtual environment (from amerlin):

   .. code-block:: bash

      lxc-create -n myimg -t download --  --dist debian --release stretch --arch amd64
      mount -o bind /dev /var/lib/lxc/myimg/rootfs/dev
      chroot /var/lib/lxc/myimg/rootfs
      rm /etc/resolv.conf
      echo "nameserver 9.9.9.9" > /etc/resolv.conf
      # distem requirements: sshd
      apt install openssh-server
      # enoslib requirements: python
      apt install -y python3
      update-alternatives --install /usr/bin/python python /usr/bin/python3 1
      # your configuration goes here
      exit
      umount /var/lib/lxc/myimg/rootfs/dev
      cd /var/lib/lxc/myimg/rootfs
      tar -czvf ../distem-stretch.tgz .

EnOSlib bootsraps distem server and agents on your nodes and start the container
for you. In particular:

    - the distem coordinator runs on one of your node (randomly picked)
    - one SSH keypair is generated for the inter-nodes connectivity and the vnodes external access
    - EnOSlib SSH connection to the vnodes are tunneled through the coordinator
      node (make sure to do the same if you want to SSH manually)
    - One single network (slash_22) is currently supported (https://gitlab.inria.fr/discovery/enoslib/issues/38)
    - ``flavour`` configuration is ignored currently (https://gitlab.inria.fr/discovery/enoslib/issues/37)
