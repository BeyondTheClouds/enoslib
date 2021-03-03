**************************************************
EnOSlib: Surviving the ☆homoterogeneous☆ world
**************************************************

|Build Status| |License| |Pypi|


What the ☆homoterogeneous☆ ?
----------------------------

Distributed systems practitioners on bare-metal testbeds know it: resources
(e.g. computes, networks) on a bare-metal infrastructure may have these slight
differences between each others that experimental code can become hairy. For
such code, achieving practical portability (e.g changing the infrastructure
parameters) is thus a tedious time consuming task.


☆Homoterogeneous☆ has been coined to express the gap between the idea
we have of a computing infrastructure, where resources have
static/predictable setup, and the reality of interacting with them on a daily
basis.

EnOSlib smoothes the experimenter's code dealing with various platforms (e.g.
local machine, scientific testbed, virtualized environments). It helps in
deploying various piece of software (e.g instrumentation, observability
tools). It also integrates well with interactive development environment like
Jupyter.

The software
------------

EnOSlib has been initially developed in the context of the `Discovery
<https://beyondtheclouds.github.io/>`_ initiative and is released under the
GPLv3 licence. It's a library written in Python: you are free to import it in
your code and cherry-pick any of its functions.

At a glance
-----------

.. raw:: html

   <script id="asciicast-iVBbJPeoWA8botcQXPcNGEac3" src="https://asciinema.org/a/iVBbJPeoWA8botcQXPcNGEac3.js" data-speed="3" async></script>


Links
-----

- Documentation: https://discovery.gitlabpages.inria.fr/enoslib/
- Source: https://gitlab.inria.fr/discovery/enoslib
- Chat: https://framateam.org/enoslib


.. |Build Status| image:: https://gitlab.inria.fr/discovery/enoslib/badges/master/pipeline.svg
   :target: https://gitlab.inria.fr/discovery/enoslib/pipelines

.. |License| image:: https://img.shields.io/badge/License-GPL%20v3-blue.svg
   :target: https://www.gnu.org/licenses/gpl-3.0

.. |Pypi| image:: https://badge.fury.io/py/enoslib.svg
   :target: https://badge.fury.io/py/enoslib

.. |Gitter| image:: https://badges.gitter.im/BeyondTheClouds/enoslib.svg
   :alt: Join the chat at https://gitter.im/BeyondTheClouds/enoslib
   :target: https://gitter.im/BeyondTheClouds/enoslib?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge

.. |Coverage| image:: https://gitlab.inria.fr/discovery/enoslib/badges/master/coverage.svg
   :target: https://sonarqube.inria.fr/sonarqube/dashboard?id=discovery%3Aenoslib%3Adev
