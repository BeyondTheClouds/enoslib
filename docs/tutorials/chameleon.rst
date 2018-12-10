Tutorial 5 - Working with Chameleon
===================================

This tutorial will let you get started using |enoslib| and Chameleon. This will
present you the bare minimum to install the library with the required dependencies.

Installation
------------

.. code-block:: bash

    $ pip install enoslib[chameleon]

.. note::

  It's a good practice to use a virtualenv or a python version manager like `pyenv`.



Basic example
-------------

The following reserve 2 nodes on the chameleon baremetal infrastructure.
Prior to the execution you must source your openrc file:

.. code-block:: bash

   $ source CH-XXXXX.sh


You must also configure an access key in you project and replace with its name
in the following.


.. literalinclude:: chameleon/tuto_chameleonbaremetal.py
   :language: python
   :linenos:


.. note::

   Similarly to other provider the configuration can be generated
   programmatically instead of using a dict.
