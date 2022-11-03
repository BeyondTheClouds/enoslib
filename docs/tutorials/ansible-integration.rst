.. _integration-with-ansible:

*******************
Ansible Integration
*******************

.. contents::
   :depth: 2

|enoslib| uses internally Ansible to perform some predefined tasks (e.g remote
commands ). But in |enoslib| we prefer not leaving the Python world :) so we've
exposed some convenient functions that use Ansible behind the scene like:

* run a single command on a subset of the nodes and gather the outputs (and errors)
* or run a set of actions (Ansible Modules) programmatically


.. hint::

   The presented methods are provider agnostic.


Run a single command on nodes and gather results
================================================

Let's consider the following script :

.. literalinclude:: ansible-integration/run_command.py
   :language: python
   :linenos:

- :py:func:`~enoslib.api.run_command` takes at least 2 parameters :

  - the actual command to run
  - the :py:class:`~enoslib.objects.Roles` (as returned by the provider
    init method), or an iterable of :py:class:`~enoslib.objects.Host`, or
    a single Host

- A :py:class:`~enoslib.api.Results` object is returned and allow for further filtering.


Run a set of actions on nodes
=============================


Using python exclusively
------------------------


Let's consider the following script:

.. literalinclude:: ansible-integration/flent_on.py
   :language: python
   :linenos:

:download:`flent_on.py <ansible-integration/flent_on.py>`

In this example each :py:class:`~enoslib.api.actions` block run a playbook
generated from the ansible module calls made.  Any ansible module can be
called here, the exact keyword arguments to pass depend on each module and
you'll need to refer to the ansible modules documentation (e.g
https://docs.ansible.com/ansible/latest/modules/apt_module.html).


Re-using results from a previous task
-------------------------------------

To access results from previous tasks, you need to start a new
:py:class:`~enoslib.api.actions` block.  Here is an example with `Garage
<https://garagehq.deuxfleurs.fr>`_:

.. literalinclude:: ansible-integration/garage.py
   :language: python
   :linenos:

:download:`garage.py <ansible-integration/garage.py>`

:download:`garage.toml.j2 <ansible-integration/garage.toml.j2>`


Using a yaml playbook
---------------------

In addition to run custom command on nodes, |enoslib| can trigger
predefined playbook stored in your filesystem. This lets you use the
native Ansible syntax to describe your tasks or launch an existing
playbook.

Let's consider the following script:

.. literalinclude:: ansible-integration/run_ansible.py
   :language: python
   :linenos:

:download:`run_ansible.py <ansible-integration/run_ansible.py>`

And the corresponding minimal playbook ``site.yml``:

.. literalinclude:: ansible-integration/site.yml
   :language: yaml
   :linenos:

:download:`site.yml <ansible-integration/site.yml>`


What's next ?
=============

If you aren't familiar with Ansible, we encourage you to go through the `Ansible
documentation <https://docs.ansible.com/ansible/latest/index.html>`_, write your own playbooks, or integrate one existing from
`ansible galaxy <https://galaxy.ansible.com/>`_.
