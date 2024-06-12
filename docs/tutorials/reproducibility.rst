.. _reproducible-experiments:

************************
Reproducible experiments
************************

.. contents::
   :depth: 2

`Reproducibility <https://en.wikipedia.org/wiki/Reproducibility>`_ is
becoming more and more important in computer science.  There are several
techniques to ensure your experiments done with Enoslib can stay
reproducible in the long term.


Setting up a reproducible environment
=====================================

Use a specific version of Enoslib
---------------------------------

Enoslib evolves over time, adding functionality but sometimes also
breaking backwards compatibility.  As a minimum, you should constrain the
version of Enoslib used for your experiment, for instance:

.. code-block:: shell

    pip install "enoslib>=8.0.0,<9.0.0"

Use a virtualenv and freeze dependencies
----------------------------------------

Going further, you might want to use a fixed version of Enoslib **and**
its dependencies (in particular, Ansible).  When setting up your
experiment:

.. code-block:: shell

    python3 -m venv ./myvenv
    . ./myvenv/bin/activate
    python3 -m pip install enoslib
    # python3 -m pip install any-other-dependency
    python3 -m pip freeze > requirements.txt

Commit this ``requirements.txt`` file in the repository of your
experiment.  Then, whenever you or somebody else tries to reproduce the
experiment:

.. code-block:: shell

    python3 -m venv ./myvenv
    . ./myvenv/bin/activate
    python3 -m pip install -r requirements.txt

Don't forget to document all these steps.  You should also document which
version of Python you used to run your experiment.

Using Guix
----------

As an alternative to the above you can use the `GNU/Guix
<https://guix.gnu.org/>`_ system to manage your software environment.  |enoslib|
is known in Guix as ``python-enoslib``.

.. code-block:: shell

    # spawn a one-off shell to run myscript.py
    guix shell python python-enoslib -- python3 myscript.py


.. note::

    - Refer to the Guix documentation to get started on your environment.
    - On Grid'5000 you can refer to the `dedicated tutorial <https://www.grid5000.fr/w/Guix>`_ to get started.


Reproducible experiments with Enoslib
=====================================

Storing experiment parameters
-----------------------------

Many experiments have parameters: which software version to install, which
mode of operation or algorithm to use, how many nodes, which base OS...

For reproducibility, it is recommended to write down these parameters in a
separate configuration file for each experiment run, and commit each
configuration file in your git repository.  Example:

.. literalinclude:: reproducibility/reproducible_parameters.yaml
    :language: yaml

:download:`reproducible_parameters.yaml <reproducibility/reproducible_parameters.yaml>`

For convenience, the format of the "g5k" list is exactly the format that
Enoslib expects to reserve machines, but you are free to use any format.

Then you would parse this parameters file in your experiment script:

.. literalinclude:: reproducibility/reproducible_parameters.py
    :language: python
    :linenos:

:download:`reproducible_parameters.py <reproducibility/reproducible_parameters.py>`


Storing logs and output
-----------------------

Similarly, logs and outputs of your experiment should be stored for
long-term archival.  Here is an example showing how to configure logging
to a file:

.. literalinclude:: reproducibility/reproducible_output.py
    :language: python
    :linenos:

:download:`reproducible_output.py <reproducibility/reproducible_output.py>`

The results of your experiments should then be committed to git.

Resources selection
-------------------

When using hardware resources on supported platforms, try to make sure
that they will remain available in the future.

Example for Grid'5000:

* Let's assume you need 25 identical nodes for your experiment
* You initially decide to use the `uvb cluster in Sophia
  <https://www.grid5000.fr/w/Sophia:Hardware#uvb>`_
* However, there are several issues: there are 30 nodes in the cluster,
  but `several nodes are temporarily down because of hardware issues
  <https://intranet.grid5000.fr/oar/Sophia/drawgantt-svg/?filter=uvb%20only>`_.
  In addition, the cluster has been installed more than 10 years ago
  (2011), so it will likely experience more hardware failures in the
  coming years.
* Overall, it is likely that fewer than 25 nodes of this cluster will
  remain available in a few years; the whole cluster might even be
  decommissioned at some point.
* In the end, you should use a larger and more recent cluster!


Software environment on nodes
-----------------------------

Make sure to deploy a specific OS environment on your nodes.  For instance
on Grid'5000, to start with a very minimal Ubuntu 20.04 environment:

.. literalinclude:: reproducibility/reproducible_g5k_simple.py
    :language: python
    :linenos:

:download:`reproducible_g5k_simple.py <reproducibility/reproducible_g5k_simple.py>`


Managing third-party software
=============================

When installing third-party software, make sure to install a fixed
version.  You can also specify the version as a parameter of your
experiment.

Third-party software distributed as source code
-----------------------------------------------

If you download and build third-party software, you can download it from
https://www.softwareheritage.org/ to be certain of its future
availability.

Third-party software distributed as binaries
--------------------------------------------

Example with a software that is directly downloaded from a website:

.. code-block:: python

    GARAGE_VERSION = parameters["garage_version"]
    logging.info("Installing Garage version %s", GARAGE_VERSION)
    GARAGE_URL = (
        f"https://garagehq.deuxfleurs.fr/_releases/v{GARAGE_VERSION}/"
         "x86_64-unknown-linux-musl/garage"
    )
    with en.actions(roles=roles["garage"]) as p:
        p.get_url(
            url=GARAGE_URL,
            dest="/tmp/garage",
            mode="755",
            task_name="Download garage",
        )

If you are unsure that this specific version of the software will stay
available in the future, you can download it locally, commit it in your
experiment repository, and use this local version in your experiment:

.. code-block:: shell

    mkdir -p artifacts
    VERSION="0.7.3"
    wget -O artifacts/garage-amd64-${VERSION} "https://garagehq.deuxfleurs.fr/_releases/v${VERSION}/x86_64-unknown-linux-musl/garage"
    git add artifacts/*
    git commit -m "Add artifacts"


.. code-block:: python

    from pathlib import Path

    GARAGE_VERSION = parameters["garage_version"]
    GARAGE_FILENAME = f"garage-amd64-{GARAGE_VERSION}"
    logging.info("Installing Garage version %s from local copy", GARAGE_VERSION)
    GARAGE_LOCAL_FILE = str(Path(__file__).parent / "artifacts" / GARAGE_FILENAME)
    with en.actions(roles=roles["garage"]) as p:
        p.copy(
            src=GARAGE_LOCAL_FILE,
            dest="/tmp/garage",
            mode="755",
            task_name="Copy garage binary",
        )

.. note::

   If the artifact is large and/or you have many nodes, it may take a long
   time to copy it to all nodes.  In that case, you could copy it first to
   a single node, and then distribute it to other nodes from there (using
   scp or a small web server).

Alternatively, you could deposit the artifact on a long-term storage
platform such as `Zenodo <https://zenodo.org/>`_, after making sure that
the license allows you to do so.

Debian packages snapshot
------------------------

Debian provides "snapshots" of its repository at
http://snapshot.debian.org This is useful if you want to really make sure
that your experiment will always use the same exact Debian packages.

.. literalinclude:: reproducibility/reproducible_g5k_full.py
    :language: python
    :linenos:

:download:`reproducible_g5k_full.py <reproducibility/reproducible_g5k_full.py>`


Experiment's shareability
=========================

Sharing experiment requires packaging it and sharing it somehow.
A proof of concept using |enoslib| for a Multi-platform Edge-to-Cloud Experiment
Workflow is available as an artifact of the `Trovi/Jupyter
<https://www.chameleoncloud.org/experiment/share/347adbf3-7c14-4834-b802-b45fdd0d9564>`_
platform of Chameleon. This work is part of `Daniel
Rosendo <https://team.inria.fr/kerdata/daniel-rosendo/>`_ 's work on
reproducibility of edge to cloud experiments.


Going further
=============

Do you have more ideas to make experiments with Enoslib reproducible?
Come tell us! |chat|
