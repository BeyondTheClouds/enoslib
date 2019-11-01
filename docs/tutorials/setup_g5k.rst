Installation
============

On Grid'5000, you can go with a virtualenv :

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


With the above you can access the Grid'5000 API from you local machine aswell.


External access
---------------

If you want to control you experiment from the outside of Grid'5000 (e.g from your local machine) you can refer to the following. You can jump this section if you work from inside Grid'5000.

SSH external access
^^^^^^^^^^^^^^^^^^^

- Solution 1: use the `Grid'5000 VPN <https://www.grid5000.fr/w/VPN>`_
- Solution 2: configure you ``~/.ssh/config`` properly:

::


   Host *.grid5000.fr
   ProxyCommand ssh -A <login>@194.254.60.33 -W "$(basename %h):%p"
   User <login>
   ForwardAgent yes


Accessing HTTP services inside Grid'5000
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to control you experiment from the outside of Grid'5000 (e.g from your local machine). For instance the Distem provider is starting a web server to handle the client requests. In order to access it propertly externally you drom your local machine can either

- Solution 1 (general): use the `Grid'5000 VPN <https://www.grid5000.fr/w/VPN>`_
- Solution 2 (HTTP traffic only): create a socks tunnel from your local machine   to Grid'5000
   ::


      # on one shell
      ssh -ND 2100 access.grid5000.fr

      # on another shell
      export https_proxy="socks5h://localhost:2100"
      export http_proxy="socks5h://localhost:2100"

      # Note that browsers can work with proxy socks
      chromium-browser --proxy-server="socks5://127.0.0.1:2100" &

- Solution 3 (ad'hoc): create a forwarding port tunnel

   ::


      # on one shell
      ssh -Nl 3000:paravance-42.rennes.grid5000.fr:3000 access.grid5000.fr

      # Now all traffic that goes on localhost:3000 is forwarded to paravance-42.rennes.grid5000.fr:3000



