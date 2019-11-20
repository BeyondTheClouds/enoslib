.. _network_emulation:

Network Emulation
=================

.. contents::
   :depth: 2

This tutorial illustrates how network constraints can be enforced using |enoslib|.
For a complete reference you can refer to :ref:`api`.


Example
-------

The example is based on the G5K provider, but can be adapted to another one if desired.
Additionally, the network constraints are heterogeneous between nodes.

.. literalinclude:: network_emulation/tuto_network_emulation.py
   :language: python
   :linenos:
 
