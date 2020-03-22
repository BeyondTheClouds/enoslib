EnosLib
=======

|Build Status| |License| |Pypi|

* Documentation: https://discovery.gitlabpages.inria.fr/enoslib/
* Source: https://gitlab.inria.fr/discovery/enoslib
* Chat: https://framateam.org/enoslib

EnOSlib is a library to help you with your experiments. The main parts of your
experiment logic is made **reusable** by the following EnOSlib building blocks:

- **Reusable infrastructure configuration**: The provider abstraction allows you to
  run your experiment on different environments (locally with Vagrant, Grid'5000,
  Chameleon and more)
- **Reusable software provisioning**: In order to configure your nodes, EnOSlib
  exposes different APIs with different level of expressivity.
  For instance EnOSlib's modules let you run remote atomic actions safely on remote
  hosts while EnOSlib's services can deploy complex software stacks with few lines
  of code.
- **Reusable experiment facilities**: Tasks help you to organize your
  experimentation workflow.

EnOSlib is designed for experimentation purpose: benchmark in a controlled
environment, academic validation ...

EnOSLib has been initially developed in the context of the
`Discovery <https://beyondtheclouds.github.io/>`_ initiative

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
