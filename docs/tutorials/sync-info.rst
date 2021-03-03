***************************
Syncing Hosts' informations
***************************

.. contents::
   :depth: 2

Currently syncing the hosts' informations will update all of the Host
datastructures with some specific data about them (e.g network IPs, processor
information). This let's the user code to take decisions based on those
informations.

.. note::

   The synchronisation is based on Ansible facts gathering and it somehow
   makes the Ansible facts available to the experimenter's python code. It comes
   at the cost of making a connection to every single host (which can be
   heavy when managing thousands of hosts).

   Also, in the future, we expect some providers to fill an initial version of
   the updated attribute to avoid a full sync. For instance, on Grid'5000
   many informations can be retrieved from the REST API.


Examples
--------

.. literalinclude:: sync-info/tuto_sync_info.py
   :language: python
   :linenos:
