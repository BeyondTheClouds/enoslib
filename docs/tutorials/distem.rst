.. _distem:

Provider::Distem
================

This tutorial leverages the ``Distem`` provider: a provider that creates
containers for you on Grid'5000.

.. note::

    More details on : http://distem.gforge.inria.fr/


.. hint::

   For a complete schema reference see :ref:`distem-schema`

.. include:: ./setup_g5k.rst


Basic example
-------------

We'll imagine a system that requires 50 compute machines and 1 controller machines.
We express this using the Distem provider:

.. hint::

   - If you don't have any image :
   
   - $) wget 'http://public.nancy.grid5000.fr/~amerlin/distem/distem-fs-jessie.tar.gz' -P /home/public

.. literalinclude:: distem/tuto_distem.py
   :language: python
   :linenos:


EnOSlib bootsraps distem server and agents on your nodes and start the container for you. In particular:

    - the distem coordinator runs one of your node (randomly picked)
    - one SSH keypair is generated for the inter-nodes connectivity and the vnodes external access
    - EnOSlib SSH connection to the vnodes are tunneled through the coordinator node (make sure to do the same if you want to SSH manually)
