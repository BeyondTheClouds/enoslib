.. _tasks:

Tutorial 5 - Using the Tasks API
================================

In this tutorial, you will learn how to organize your code into tasks and
integrate it with a command line interface.

For the sake of illustration, let's consider the following scenario:

- Get machines from vagrant
- Apply some network constraints between your machines
- Validate those network constraints

Installation
------------

.. code-block:: bash

    $ pip install enoslib

.. note::

  It's a good practice to use a virtualenv or python version manager like `pyenv`_.

Using the API
-------------

The following ``enos.py`` implements the desired workflow.

.. literalinclude:: using-tasks/step1.py
   :language: python
   :linenos:

- Lines 5-18 describe the wanted resources. Here we want two machines with roles
  ``control`` and ``compute`` respectively. These two nodes will have one network card
  configured using the same network whose role is ``n1``.

  .. note::

    Machine roles and network roles are transparent to the |enoslib|. The semantic is
    left to the application using it.

- Lines 19-23 describe some network constraints. Those constraints will be set
  between the nodes of the two groups ``control`` and ``compute`` on the network
  ``n1``.

- Lines 27-34 enforce the wanted workflow.

  .. note::

    Under the hoods, |enoslib| leverages Ansible for many routine tasks and
    thus an inventory must be generated. This is exactly the purpose of
    :py:func:`enoslib.api.generate_inventory` function.  When
    ``check_networks`` is set, |enoslib| will auto-discover the mapping between
    the network roles and the available network interfaces. This is convenient
    when it comes to deal with non uniform (or non deterministic) network cards
    naming.


- You can launch the script using :

  .. code-block:: bash

      $ python enos.py


- The content of the generated inventory should looks like the following:

  .. literalinclude:: using-tasks/hosts
     :language: python

- You can check the generated reports by :py:func:`enoslib.api.validate_network` in ``_tmp_enos_``.


  .. literalinclude:: using-tasks/_tmp_enos_/enos-0.out
     :language: python
     :emphasize-lines: 2

Using tasks
-----------


.. literalinclude:: using-tasks/step2.py
   :language: python
   :emphasize-lines: 33,45,51
   :lines: 33-65

- Using Tasks is a neat way to organize your program into a workflow.

- The environment (``env`` variable in the above) is a way to (1) store
  information on the current execution and (2) pass information from one task
  to another. It is automatically restored at the beginning of a task and saved
  at the end.


- You can launch the script using :

  .. code-block:: bash

    $ python enos.py


Integrating with a command line parser
--------------------------------------

Let's integrate our tasks with a command line parser. Here we choose `click`_.
First ensure that it is installed:

.. code-block:: bash

    $ pip install click

- Change the content of ``enos.py`` to the following:

  .. literalinclude:: using-tasks/step3.py
     :language: python
     :lines: 32-75

- For the sake of illustration, we added a flag (``--force``) to the command
  line which allows to force the recreation of the virtual machines (see
  :py:meth:`enoslib.infra.provider.Provider.init`).  Since every provider
  supports this flag we pass its value to the ``ìnit`` method.

- You will now have access to the command line interface :

  .. code-block:: bash

      $ python enos.py --help
      Usage: enos.py [OPTIONS] COMMAND [ARGS]...

      Options:
        --help  Show this message and exit.

      Commands:
        emulate   Emulates the network.
        up        Starts a new experiment using vagrant
        validate  Validates the network constraints.

.. _click: http://click.pocoo.org/
.. _pyenv: https://github.com/pyenv/pyenv
