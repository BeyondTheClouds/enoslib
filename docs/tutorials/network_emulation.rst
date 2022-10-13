.. _network_emulation:

Network Emulation
=================

.. contents::
   :depth: 2

This tutorial illustrates how network constraints can be enforced using |enoslib|.
Another resources can be found in the :ref:`emul`.

Setting up homogeneous constraints
-----------------------------------

When all your nodes share the same network limitations you can use the
`Netem` service.

.. literalinclude:: network_emulation/tuto_svc_netem.py
   :language: python
   :linenos:

Setting up heterogeneous constraints
-------------------------------------

You can use the HTBNetem service for this purpose. The example is based on the
G5K provider, but can be adapted to another one if desired.


- Build from a dictionary:

    .. literalinclude:: ../tutorials/network_emulation/tuto_svc_htb.py
        :language: python
        :linenos:

- Build a list of constraints iteratively

    .. literalinclude:: ../tutorials/network_emulation/tuto_svc_htb_build.py
        :language: python
        :linenos:

- Using a secondary network

    .. literalinclude:: ../tutorials/network_emulation/tuto_svc_htb_secondary.py
        :language: python
        :linenos:

- Using a secondary network from a list of constraints

    .. literalinclude:: ../tutorials/network_emulation/tuto_svc_htb_b_second.py
        :language: python
        :linenos:


Working at the network device level
-----------------------------------

If you know the device on which limitations will be applied you can use the
functions ``netem`` or ``netem_htb``.

.. literalinclude:: network_emulation/tuto_netem.py
   :language: python
   :linenos:

.. literalinclude:: network_emulation/tuto_netem_htb.py
   :language: python
   :linenos:
