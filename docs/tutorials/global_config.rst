.. _global_config:

********************
Global configuration
********************

Enoslib provides a mechanism to set global configuration options to change
its behaviour.

Number of Ansible forks
=======================

.. note::

  This is only supported since Enoslib 8.2.0.  Previous versions had a
  fixed number of forks set to 100.

This controls the `forks`_ parameter of Ansible, i.e. the level of
parallelism when running actions on nodes.  The default value is 5, the
same default as Ansible.  If you want to control a large number of nodes
and you have enough CPU and memory on the control host, you can increase
this value.  See :ref:`performance_tuning` for more discussion on
performance tuning.

.. literalinclude:: performance_tuning/vmong5k_forks.py
   :language: python
   :linenos:


Automatic SSH jump host
=======================

.. note::

  This feature has been added in Enoslib 8.1.0.

Enoslib tries to detect if it runs inside or outside of the Grid'5000
network.  When running outside, it automatically uses a SSH jump host
through ``access.grid5000.fr`` for convenience, because this is necessary
to control Grid'5000 nodes.

It is possible to force-enable or force-disable this automatic detection.
This is useful when using the Grid'5000 VPN, because Enoslib does not
detect this case and will still use the SSH jump host, even though it is
unnecessary.

When disabling ``g5k_auto_jump``, beware of any local SSH configuration in
your ``~/.ssh/config`` that will now be applied.  Previous versions of
Enoslib used to recommend setting up ``~/.ssh/config`` to setup the SSH
jump host, but this is no longer the case.  You should remove any
configuration block targeting ``*.grid5000.fr`` that you may have added
for previous versions of Enoslib.

.. literalinclude:: global_config/g5k_auto_jump.py
   :language: python
   :linenos:

Other parameters
================

All parameters are documented at :py:func:`~enoslib.config.set_config`

.. _forks: https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_strategies.html#controlling-playbook-execution-strategies-and-more
