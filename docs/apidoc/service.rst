************
Service APIs
************

Base Service Class
==================

.. automodule:: enoslib.service.service
    :members: Service

Conda & Dask
=============

Conda & Dask Service Class
--------------------------


.. automodule:: enoslib.service.conda.conda
    :members: Conda, Dask, conda_run_command, conda_run


Docker
======

Docker Service Class
--------------------


.. automodule:: enoslib.service.docker.docker
    :members: Docker

Dstat (monitoring)
==================

Dstat Service Class
--------------------


.. automodule:: enoslib.service.dstat.dstat
    :members: Dstat

K3s (container orchestration)
=============================

K3s Service Class
--------------------


.. automodule:: enoslib.service.k3s.k3s
    :members: K3s

Locust (Load generation)
========================

Locust Service Class
------------------------

.. automodule:: enoslib.service.locust.locust
    :members: Locust

Monitoring
==========

Monitoring Service Class
------------------------

.. _monitoring:


.. automodule:: enoslib.service.monitoring.monitoring
    :members: TIGMonitoring, TPGMonitoring


Network Emulation (Netem & SimpleNetem)
=======================================

.. _netem:

Netem & SimpleNetem Service Class
---------------------------------

To enforce network constraint, |enoslib| provides two different services: the
Netem Service and the SimpleNetem Service. The former tends to be used when
heterogeneous constraints are required between your hosts while the latter
can be used to set homogeneous constraints between your hosts.

Netem and SimpleNetem Class
***************************

.. automodule:: enoslib.service.netem.netem
    :members: Netem, SimpleNetem


Skydive
=======

.. _skydive:

Skydive Service Class
---------------------


.. automodule:: enoslib.service.skydive.skydive
    :members: Skydive
