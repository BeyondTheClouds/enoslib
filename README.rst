**************************************************
EnOSlib: Surviving the ☆homoterogeneous☆ world
**************************************************

|Build Status| |License| |Pypi| |Pepy| |Chat| |SW|


What the ☆homoterogeneous☆ ?
----------------------------

Distributed systems practitioners on bare-metal testbeds know it: resources
(e.g. computes, networks) on a bare-metal infrastructure may have these slight
differences between each other that experimental code can become hairy. For
such code, achieving practical portability (e.g changing the infrastructure
parameters) is thus a tedious time consuming task.


☆Homoterogeneous☆ has been coined to express the gap between the idea
we have of a computing infrastructure, where resources have
static/predictable setup, and the reality of interacting with them on a daily
basis.

In this context, EnOSlib smoothes the experimental code and can

- deal with various platforms (e.g. local machine, scientific testbed, virtualized environments)
- interact programmatically with different your remote resources: compute
  (servers, containers) and networks (ipv4, ipv6)
- deploy *ready-to-use* experimentation services (e.g instrumentation, observability tools).
- emulate complex network topologies (e.g for your FOG experiments)
- integrate your code with interactive development environment like Jupyter.


.. |Build Status| image:: https://gitlab.inria.fr/discovery/enoslib/badges/main/pipeline.svg
   :target: https://gitlab.inria.fr/discovery/enoslib/pipelines

.. |License| image:: https://img.shields.io/badge/License-GPL%20v3-blue.svg
   :target: https://www.gnu.org/licenses/gpl-3.0

.. |Pypi| image:: https://badge.fury.io/py/enoslib.svg
   :target: https://badge.fury.io/py/enoslib

.. |Pepy| image:: https://pepy.tech/badge/enoslib/week
   :target: https://pepy.tech/project/enoslib


.. |Chat| image:: https://img.shields.io/badge/mattermost-enoslib-blueviolet
   :target: https://framateam.org/enoslib/channels/town-square

.. |SW| image:: https://archive.softwareheritage.org/badge/origin/https://gitlab.inria.fr/discovery/enoslib.git/
    :target: https://archive.softwareheritage.org/browse/origin/?origin_url=https://gitlab.inria.fr/discovery/enoslib.git
