.. enoslib documentation master file, created by
   sphinx-quickstart on Thu Sep 21 21:45:39 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to EnOSlib's documentation!
===================================

EnOSlib helps you deploy applications on various platforms. 

It targets role based deployments and allows you to describe your operations
using tasks.

More pragmatically, with the EnOSlib, you can iterate on your application
deployment and experimental workflow locally before moving to a large testbed
like Grid'5000, or Chameleon. It saves time and energy.

EnOSlib is designed for experimentation purpose: benchmark in a controlled
environment, academic validation ...

.. hint ::

   The source code is available at
   https://github.com/BeyondTheClouds/enoslib


.. hint ::

   Cookiecutter template is available at
   https://github.com/msimonin/cookiecutter-enoslib.git

EnOSlib primer
==============

Let's consider a user called Alice or Bob.


{{ user }} would like to start a network benchmark between the nodes of an
infrastructure. {{ user }} chooses to go with `flent <https://flent.org/>`_ and
thus writes the following:


.. literalinclude:: tutorials/ansible-integration/flent_on.py
   :language: python
   :linenos:


This starts {{ user }}'s experiment on the local machine using Vagrant (with
libvirt). Note that a {{ user }}'s friend will be able to run the same using
``backend="virtualbox"`` if VirtualBox is installed. Now
looking at the result directory created at the end of the execution, {{ user }}
finds:

.. image:: ./result.png

{{ user }} launches several times the script, getting new results. Subsequent
runs are faster because the machines are already up and everything is
`idempotent <https://en.wikipedia.org/wiki/Idempotence>`_.

{{ user }} now would like to go in a `real` testbed (e.g Grid'5000). Good news ! {{ user }}
only have to adapt the configuration phase and the provider used in the script.
The experimentation logic can remain the same. Thus, one can write the following:


.. literalinclude:: tutorials/ansible-integration/flent_on_grid5000.py
   :language: python
   :linenos:


.. image:: ./result_g5k.png


Now where {{ user }} can go from here depends on the needs:

- Moving to another provider is possible. {{ user }} only needs to learn about the specific object for
  this configuration -- e.g see :ref:`[1] <vmong5k>`.

- Refactoring the code, providing a command line interface could be also nice.
  After all its just python code -- see :ref:`[2] <tasks>`.
  Or moving the deployment code (because it becomes large) into separated
  Ansible files -- see :ref:`[3] <integration-with-ansible>`.

- Applying specific network constraints between the nodes of the reservation is
  also possible. {{ user }}'ll need to learn more about how enforcing the constraints
  -- see :ref:`[4] <api>`.

- Contributing to this project would be wonderful. {{ user }} doesn't need to do much,
  improving the documentation would be very helpful -- see :ref:`[5] <contributing>`.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorials/index.rst
   apidoc/index.rst
   performance_tuning.rst
   theyuseit.rst
   contributing.rst
