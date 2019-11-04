.. _parameters_exploration:

**********************
Parameters exploration
**********************


This tutorial illustrates how parameters can be explored. The cornerstone here is the excellent `Execo ParamSweeper <http://execo.gforge.inria.f/>`_.
For the illustration purpose we consider the following question:

- How the network performance is impacted by concurrent network flows and different network conditions ?

To answer this question we'll simply measure the network throughput while varying the number of virtual machines pairs and network characteristics between them. For this purpose, we reserve 2 physical machines: one for the source (client) virtual machines and the other for the destination (server) virtual machines. Every single source virtual machine is then paired with its destination virtual machine. Different network delays will be applied between the sources and the destination.

.. literalinclude:: parameters_exploration/tuto_sweeper.py
   :language: python
   :linenos: