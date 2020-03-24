.. _network_emulation:

Network Emulation
=================

.. contents::
   :depth: 2

This tutorial illustrates how network constraints can be enforced using |enoslib|.
Another resources can be found in the :ref:`netem`.

Setting up homogeneous constraints
-----------------------------------

When all your nodes share the same network limitations you can use the
`SimpleNetem` service.

.. literalinclude:: network_emulation/tuto_simple_netem.py
   :language: python
   :linenos:

Setting up heterogeneous constraints
-------------------------------------

You can use the Netem service for this purpose. The example is based on the
G5K provider, but can be adapted to another one if desired.

.. literalinclude:: network_emulation/tuto_network_emulation.py
   :language: python
   :linenos:
