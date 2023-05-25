Installation
============

To use Grid'5000 with Enoslib, you can go with a virtualenv :

.. code-block:: bash

    $ virtualenv -p python3 venv
    $ source venv/bin/activate
    $ pip install -U pip

    $ pip install enoslib


Configuration
=============

Since `python-grid5000 <https://pypi.org/project/python-grid5000/>`_ is used
behind the scene, the configuration is read from a configuration file located in
the home directory. It can be created with the following:

::

   echo '
   username: MYLOGIN
   password: MYPASSWORD
   ' > ~/.python-grid5000.yaml

   chmod 600 ~/.python-grid5000.yaml


The above configuration should work both from a Grid'5000 frontend machine
and from your local machine as well.


External access (from your laptop)
----------------------------------

If you are running your experiment from outside Grid'5000 (e.g. from your local
machine), `using a SSH jump host is required <https://www.grid5000.fr/w/Getting_Started#Recommended_tips_and_tricks_for_an_efficient_use_of_Grid.275000>`_.
Enoslib (version 8.1.0 and above) will automatically setup such a SSH jump
host connection through ``access.grid5000.fr``.

.. hint::

   This SSH setup might not work properly if you want to control a
   larger number of nodes (around 14 or more), because it generates too
   many SSH connections on the Grid'5000 jump host.  Please report any
   issue you face `on the dedicated bug report
   <https://gitlab.inria.fr/discovery/enoslib/-/issues/147>`_.  In the
   meantime, the workaround is to work directly inside Grid'5000.
