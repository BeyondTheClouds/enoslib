.. _distem:

Provider::Distem
================

This tutorial leverages the ``Distem`` provider: a provider that creates
containers for you on Grid'5000.


.. hint::

   For a complete schema reference see :ref:`distem-schema`

.. include:: ./setup_g5k.rst


To accesss your virtual machines from your local machine, see below.


Basic example
-------------

We'll imagine a system that requires 50 compute machines and 1 controller machines.
We express this using the Distem provider:

.. literalinclude:: distem/tuto_distem.py
   :language: python
   :linenos:


.. note::

   You can access to each container with SSH.
