.. _static:

****************
Provider::Static
****************

.. contents::
   :depth: 2

The static provider of |enoslib| lets you use a bunch of resources of you own.
For instance you have a bunch of Raspberry Pis and would like to run some
experiments on them.


.. hint::

   For a complete schema reference see :ref:`static-schema`

Basic example
=============

Assuming that you have two machines and a network, you can describe your
infrastructure like the following:

.. literalinclude:: static/tuto_static.py
   :language: python
   :linenos:

More generally, you'll have to describe exhaustively what you have.

Advanced usage: combining |enoslib| projects
============================================

Let's assume you want have access to two |enoslib| projects and you are using
Grid'5000. You can use both projects using a single reservation by leveraging
the static provider of each project. Here is a sketch of the workflow you can
use:

- merge the resource claim of both projects
- make one call to the Grid'5000 provider
- split the roles and networks given back by the provider
- instantiate two static provider (one for each sub-project) with the
  corresponding resources description.
