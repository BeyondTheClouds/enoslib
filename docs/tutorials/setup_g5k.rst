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

If you want to control your experiments from outside Grid'5000 (e.g from
your local machine) you can refer to the following.  Jump this section if
you only plan to work from inside Grid'5000.

- Solution 1: use the `Grid'5000 VPN <https://www.grid5000.fr/w/VPN>`_
- Solution 2: configure your ``~/.ssh/config`` properly:

::


   Host !access.grid5000.fr *.grid5000.fr
      User <login>
      ProxyJump <login>@access.grid5000.fr
      StrictHostKeyChecking no
      UserKnownHostsFile /dev/null
      ForwardAgent yes

.. hint::

   This SSH configuration might not work properly if you want to control a
   larger number of nodes (around 14 or more), because it generates too
   many SSH connections on the Grid'5000 jump host.  Please report any
   issue you face `on the dedicated bug report
   <https://gitlab.inria.fr/discovery/enoslib/-/issues/147>`_.  In the
   meantime, the workaround is to use the Grid'5000 VPN or to work
   directly inside Grid'5000.
