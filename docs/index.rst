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


This starts Alice's experiment on her local machine using Vagrant. Looking at
the result directory created at the end of the execution, Alice finds:

.. image:: ./result.png


Since the experimentation code seems ok, Alice now would like to go in a `real`
testbed (e.g Grid'5000). She only have to adapt the configuration phase and the
provider used in her script. The experimentation logic can remain the same.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorials/index.rst
   apidoc/index.rst
   theyuseit.rst
   contributing.rst


 
