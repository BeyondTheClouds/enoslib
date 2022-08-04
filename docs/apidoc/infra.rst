*************
Provider APIs
*************

Base Provider Class
===================

.. automodule:: enoslib.infra.provider
    :members:
    :undoc-members:
    :show-inheritance:


Vagrant
=======

Vagrant Provider Class
----------------------

.. automodule:: enoslib.infra.enos_vagrant.provider
    :members: Enos_vagrant

.. _vagrant-schema:

Vagrant Schema
--------------

.. literalinclude:: ../../enoslib/infra/enos_vagrant/schema.py


Grid5000 (G5k)
==============

G5k Provider Class
------------------

.. automodule:: enoslib.infra.enos_g5k.provider
    :members: G5k, G5kHost, G5kNetwork, G5kVlanNetwork, G5kProdNetwork, G5kSubnetNetwork, G5kTunnel

.. _grid5000-schema:

G5k Schema
----------

.. literalinclude:: ../../enoslib/infra/enos_g5k/schema.py


G5k API utils
-------------

.. automodule:: enoslib.infra.enos_g5k.g5k_api_utils
    :members:
    :undoc-members:


Virtual Machines on Grid5000 (VMonG5k)
======================================

VMonG5k Provider Class
----------------------

.. automodule:: enoslib.infra.enos_vmong5k.provider
    :members: VirtualMachine, start_virtualmachines, mac_range

.. _vmong5k-schema:

VMonG5k Schema
--------------

.. literalinclude:: ../../enoslib/infra/enos_vmong5k/schema.py


Containers on Grid5000 (Distem)
===============================

Distem Provider Class
---------------------

.. automodule:: enoslib.infra.enos_distem.provider
    :members: Distem

.. _distem-schema:

Distem Schema
-------------

.. literalinclude:: ../../enoslib/infra/enos_distem/schema.py


Static
======

Static Provider Class
---------------------

.. automodule:: enoslib.infra.enos_static.provider
    :members: Static

.. _static-schema:

Static Schema
-------------

.. literalinclude:: ../../enoslib/infra/enos_static/schema.py


Openstack
=========

Openstack Provider Class
------------------------

.. automodule:: enoslib.infra.enos_openstack.provider
    :members: Openstack

.. _openstack-schema:

Openstack Schema
----------------

.. literalinclude:: ../../enoslib/infra/enos_openstack/schema.py


Chameleon
=========

Chameleon(kvm) Provider Class
-----------------------------

.. automodule:: enoslib.infra.enos_chameleonkvm.provider
    :members: Chameleonkvm

Chameleon(kvm) Schema
---------------------

.. literalinclude:: ../../enoslib/infra/enos_chameleonkvm/schema.py

Chameleon(bare metal) Provider Class
------------------------------------

.. automodule:: enoslib.infra.enos_chameleonbaremetal.provider
    :members: Chameleonbaremetal

Chameleon(bare metal) schema
----------------------------

.. literalinclude:: ../../enoslib/infra/enos_chameleonkvm/schema.py

FIT/IoT-LAB
==============

.. _iotlab-schema:

FIT/IoT-LAB Schema
----------

.. literalinclude:: ../../enoslib/infra/enos_iotlab/schema.py

Sensor
------

.. literalinclude:: ../../enoslib/infra/enos_iotlab/objects.py


Providers Class
===============

.. automodule:: enoslib.infra.providers
    :members:
    :undoc-members:
    :show-inheritance:

