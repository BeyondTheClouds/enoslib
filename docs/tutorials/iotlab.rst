*********************
Provider::FIT/IoT-LAB
*********************

.. contents::
   :depth: 2

This tutorial illustrates the use of EnOSlib to interact with FIT/IoT-LAB testbed.

.. hint::

   For a complete schema reference see :ref:`iotlab-schema`

.. hint::


.. include:: ./setup_iotlab.rst


Basic examples
==============


Getting started tutorial
------------------------

This script implements a similar behavior as the getting started tutorial from
FIT/IoT-LAB (https://www.iot-lab.info/legacy/tutorials/getting-started-tutorial/index.html).


**Requirement**: M3 image (*tutorial_m3.elf*)

- The M3 image can be download from the website: https://www.iot-lab.info/testbed/resources/firmware.
- It is available at the "Presets tab" under the name *iotlab_m3_tutorial*.
- Download and save it in the same folder as the script.


.. literalinclude:: iotlab/tuto_iotlab_getting_started.py
   :language: python
   :linenos:

.. note::

   The test creates a thread to read serial while the test ask the sensor to send messages.
   We don't recommend doing this in your tests. Anyway, this is necessary in this example since
   the getting started tutorial supposes the user interaction.

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_iotlab_getting_started.py


Using A8 nodes
--------------

This script shows how to use the A8 node available in the platform.
They have a Linux OS installed, so we can access them through SSH and run simple
linux commands.


.. literalinclude:: iotlab/tuto_iotlab_a8_basic.py
   :language: python
   :linenos:

.. note::

   Note that the Linux version installed on nodes has limited capabilities.

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_iotlab_a8_basic.py


Using RPi nodes
----------------

This script shows how to use the RPI node available in the platform.
They have a Linux OS installed, so we can access them through SSH and run simple
linux commands.


.. literalinclude:: iotlab/tuto_iotlab_rpi_basic.py
   :language: python
   :linenos:

.. note::

   Note that the Linux version installed on nodes has limited capabilities.

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_iotlab_rpi_basic.py


Advanced examples
=================


Monitor M3 consumption
----------------------

Simple example of using the monitoring tools in FIT/IoT-LAB testbed.

This script implements a similar behavior as the "Monitor the consumption of M3 node
during an experiment" (https://www.iot-lab.info/legacy/tutorials/monitoring-consumption-m3/index.html).


**Requirement**: M3 image (*tutorial_m3.elf*)

- The M3 image can be download from the website: https://raw.githubusercontent.com/wiki/iot-lab/iot-lab/firmwares/tutorial_m3.elf
- Download and rename it properly, saving in the same folder as the script.

.. literalinclude:: iotlab/tuto_iotlab_m3_consumption.py
   :language: python
   :linenos:

.. note::

    The monitoring files are compressed and saved in the current folder.

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_iotlab_m3_consumption.py

- Finally, you can evaluate and plot the results as done in the tutorial.
  It uses the plot_oml_consum tool (Available at: https://github.com/iot-lab/oml-plot-tools).

    .. code-block:: bash

        $ tar xfz <expid>-grenoble.iot-lab.info.tar.gz
        $ plot_oml_consum -p -i <expid>/consumption/m3_<id>.oml


Radio Monitoring for M3 nodes
-----------------------------

Simple example of using the monitoring tools in FIT/IoT-LAB testbed.

This script implements a similar behavior as the "Radio monitoring for M3 nodes"
(https://www.iot-lab.info/legacy/tutorials/monitoring-radio-m3/index.html).


**Requirement**: M3 image (*tutorial_m3.elf*)

- Please follow the steps 1-4 in the FIT/IoT-LAB tutorial to create the image.
- Save it in the same folder as the script.
- Adjust the channels (11, 14) used during the test accordingly
  (see step 5 in the FIT/IoT-LAB tutorial).

.. literalinclude:: iotlab/tuto_iotlab_m3_radio_monitoring.py
   :language: python
   :linenos:

.. note::

    The monitoring files are compressed and saved in the current folder.

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_iotlab_m3_radio_monitoring.py

- Finally, you can evaluate and plot the results as done in the tutorial.
  It uses the plot_oml_consum tool (Available at: https://github.com/iot-lab/oml-plot-tools).

    .. code-block:: bash

        $ tar xfz <expid>-grenoble.iot-lab.info.tar.gz
        $ plot_oml_radio -a -i <expid>/radio/m3_<id>.oml


Radio Sniffer with M3 nodes
---------------------------

Simple example of using the monitoring tools in FIT/IoT-LAB testbed.

This script implements a similar behavior as the "Radio sniffer with M3 nodes"
(https://www.iot-lab.info/legacy/tutorials/monitoring-sniffer-m3/index.html).


**Requirement**: M3 image (*tutorial_m3.elf*)

- The M3 image can be download from the website:
  https://raw.githubusercontent.com/wiki/iot-lab/iot-lab/firmwares/tutorial_m3.elf
- Download and save it in the same folder as the script.

.. literalinclude:: iotlab/tuto_iotlab_m3_radio_sniffer.py
   :language: python
   :linenos:

.. note::

    The pcap file is compressed and saved in the current folder.

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_iotlab_m3_radio_sniffer.py

- Finally, you can analyze the packets with wireshark.

    .. code-block:: bash

        $ tar xfz <expid>-grenoble.iot-lab.info.tar.gz
        $ wireshark <expid>/sniffer/m3-7.pcap

.. _IoT-LAB IPv6:

IPv6 - Interacting with frontend
--------------------------------

Some tutorials in FIT/IoT-LAB run commands directly in the frontend
node. You can script this interaction using a combination of Static
and IoT-LAB providers in EnOSlib.

This script implements a similar behavior as the "Public IPv6 (6LoWPAN/RPL)
network with M3 nodes"
(https://www.iot-lab.info/legacy/tutorials/contiki-public-ipv6-m3/index.html).
This tutorial runs the tunslip tool in the frontend node to bridge packets between
the external network and M3 sensors in the platform.

**Requirement**: M3 images (*border-router.iotlab-m3* and *http-server.iotlab-m3*)

- Please follow Step 4 in the original tutorial to download the images.

.. literalinclude:: iotlab/tuto_iotlab_m3_ipv6.py
   :language: python
   :linenos:

.. note::

    IPv6 address used in M3 sensors are globally accessible.

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_iotlab_m3_ipv6.py

.. _IoT-LAB Monitoring IPv6:

Monitoring A8 nodes - IPv6
--------------------------

This example shows how to install a monitoring stack (Grafana/Prometheus/Telegraf)
on Grid'5000 and FIT/IoT-LAB nodes to collect infrastructure metrics. By using the
IPv6 network and Prometheus, we're able to collect data from both testbed. Note that
IPv6 connection from Grid'5000 to IoT-LAB is allowed (the inverse isn't true).

Summarizing, the example does the following:

- Install Grafana in a node: Grafana accepts connections in the port 3000, user: admin, password: admin.

- Install Prometheus database in a node: accessible at port 9090. It is installed
  with the following parameters (scrape_interval: 10s, scrape_timeout: 10s, eval_interval: 15s).
  They are defined at: enoslib/service/monitoring/roles/prometheus/defaults/main.yml).

- Install Telegraf on remaining nodes: Telegraf is configured to receive incoming
  connections from Prometheus at port 9273.

.. literalinclude:: iotlab/tuto_iotlab_ipv6_monitoring.py
   :language: python
   :linenos:

.. note::

    The Prometheus database is compressed and saved in the current folder.

- You can launch the script using :

    .. code-block:: bash

        $ python tuto_iotlab_ipv6_monitoring.py


Jupyter Notebooks
=================

`Grid5000 and FIT/IoT-LAB - IPv6 <iotlab/tuto_iotlab_g5k_ipv6.ipynb>`_
----------------------------------------------------------------------

