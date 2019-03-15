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

.. hint ::

   The source code is available at
   https://github.com/BeyondTheClouds/enoslib


.. hint ::

   Cookiecutter template is available at
   https://github.com/msimonin/cookiecutter-enoslib.git

EnOSlib primer
==============

Alice would like to start a network benchmark between the nodes of the
infrastructure she got access to.
She chooses to go with `flent <https://flent.org/>`_ and she writes the following:


.. literalinclude:: tutorials/ansible-integration/flent_on.py
   :language: python
   :linenos:


This starts Alice's experiment on her local machine using Vagrant (with
libvirt). Note that Alice's friend, Bob will be able to run the same using
``backend="virtualbox"`` on his machine because he prefers VirtualBox. Now
looking at the result directory created at the end of the execution, Alice
finds:

.. image:: ./result.png

Alice launches several times her script, getting new results. Subsequent runs
are faster because the machine are already up and everything is `idempotent
<https://en.wikipedia.org/wiki/Idempotence>`_.

Alice now would like to go in a `real` testbed (e.g Grid'5000). Good news ! She
only have to adapt the configuration phase and the provider used in her script.
The experimentation logic can remain the same. Thus, she writes the following:


.. literalinclude:: tutorials/ansible-integration/flent_on_grid5000.py
   :language: python
   :linenos:


.. image:: ./result_g5k.png


Now where Alice can go from here depends on her needs:

- Moving to another provider is possible. She only needs to learn about the specific object for
  this configuration -- e.g see :ref:`[1] <vmong5k>`.

- Refactoring her code, providing a command line interface could be also nice.
  After all its just python code -- see :ref:`[2] <tasks>`.
  Or moving her deployment code (because it becomes large) into separated
  Ansible files -- see :ref:`[3] <integration-with-ansible>`.

- Applying specific network constraints between the nodes of her reservation is
  also possible. She'll need to learn more about how enforcing the constraints
  -- see :ref:`[4] <api>`.

- Contributing to this project would be wonderful. She doesn't need to do much,
  improving the documentation would be very helpful -- see :ref:`[5] <contributing>`.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorials/index.rst
   apidoc/index.rst
   theyuseit.rst
   contributing.rst
