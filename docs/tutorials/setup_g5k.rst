Installation
------------

On Grid'5000, you can go with a virtualenv :

.. code-block:: bash

    $ virtualenv venv
    $ source venv/bin/activate
    $ pip install -U pip

    $ pip install enoslib


Configuration
-------------

Since `python-grid5000 <https://pypi.org/project/python-grid5000/>`_ is used
behind the scene, the configuration is read from a configuration file located in
the home directory. It can be created with the following:

::

   echo '
   username: MYLOGIN
   password: MYPASSWORD
   ' > ~/.python-grid5000.yaml


With the above you can access the Grid'5000 API from you local machine aswell.


SSH external access
-------------------

As ``~/.ssh/config`` is honored by |enoslib|, to access Grid'5000 resources from you local
machine you can configure the ssh configuration file as follows:

::


   Host *.grid5000.fr
   ProxyCommand ssh -A <login>@194.254.60.33 -W "$(basename %h):%p"
   User <login>
   ForwardAgent yes


