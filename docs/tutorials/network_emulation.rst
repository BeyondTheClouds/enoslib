.. _network_emulation:

Network Emulation
=================

This tutorial illustrates how network constraints can be enforced using |enoslib|.
For a complete reference you can refer to :ref:`api`.


Example
-------

The example is based on the VMonG5K provider, but can be adapted to another one if desired.
The delay between cities are taken from https://hal.inria.fr/hal-02048965.
In this example we map each city to a |enoslib| role and we claim one machine per role.

.. literalinclude:: network_emulation/tuto_network_emulation.py
   :language: python
   :linenos:
 
