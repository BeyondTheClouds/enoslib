Installation
============

We strongly suggest to use a virtual environment to install and run your experiments.

.. code-block:: bash

    $ python3 -m venv venv/
    $ source venv/bin/activate
    $ pip install -U pip
    $ pip install enoslib[iot]


Configuration
=============

The Iotlab provider is built on top of 2 libraries provided by the FIT/IoT-LAB
platform: **cli-tools** (https://github.com/iot-lab/cli-tools) and
**ssh-cli-tools** (https://github.com/iot-lab/ssh-cli-tools).
Underlying, these tools use the REST API to access and manipulate the platform.

To access the REST API, user must be authenticated. These tools relies on the
configuration file ".iotlabrc" located at the home directory. It can be created by
using the CLI tools, so inside the virtual environment:

::

   iotlab-auth -u USERNAME -p PASSWORD


For more details, read the documentation of iotlab-auth (*iotlab-auth -h*).


External access
---------------

Pre-requisites: Configure your SSH access to the FIT/IoT-LAB platform
(https://www.iot-lab.info/legacy/tutorials/ssh-access/index.html).

To be able to access the A8 nodes from your PC, it's necessary to configure
the proxy ssh accordingly.

- Configure you ``~/.ssh/config`` properly, example:

::

    Host *.grenoble.iot-lab.info
    ProxyCommand ssh -A <user>@grenoble.iot-lab.info -W "$(basename %h):%p"
    User <user>
    ForwardAgent yes

Remember to set the site used (e.g. grenoble).
