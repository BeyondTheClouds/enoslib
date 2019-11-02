.. _integration-with-ansible:

***************************
Executing commands on nodes
***************************

.. contents::
   :depth: 2

|enoslib| uses internally Ansible to perform some predefined tasks (e.g network
emulation). The APIs allowing this are exposed so that anyone can use them.
User can thus :

* run a single command on a subset of the nodes and gather the outputs (and erros)
* or run a set of actions ( ansible playbook) programmatically


.. hint::

   The presented methods are provider agnostic.


Run a single command on nodes and gather results
================================================

Let's consider the following script :

.. literalinclude:: ansible-integration/run_command.py
   :language: python
   :linenos:
   :emphasize-lines: 32

- :py:func:`~enoslib.api.run_command` takes at least 3 parameters :

    - (mandatory)the actual command to run

    - the host pattern (see
      https://docs.ansible.com/ansible/latest/intro_patterns.html)
      This allow to further filter on which nodes the command will be run.

    - the roles (as returned by the provider init method) or the path to the inventory

- The ``result`` variable is a dict containing the results of the execution of the
  command.
- Inspecting the ``ok`` key will give you the stderr and stdout where the commands
  where successfully launched.

.. literalinclude:: ansible-integration/result_ok
   :language: javascript
   :linenos:

- Inspecting the ``failed`` key will give you the failed hosts. Hosts that were
  unreachable or the hosts on which the command the command failed (e.g syntax
  error).

- An extra key ``result`` is available and will give you the raw results that
  the internal Ansible APIs would have give you if using directly.


Run a set of actions on nodes
=============================

Using python exclusively
------------------------

Let's consider the following script:

.. literalinclude:: ansible-integration/flent_on.py
   :language: python
   :linenos:
   :emphasize-lines: 24-40

In this example each ``play_on`` block run a playbook generated from the ansible
module calls made.
Any ansible module can be called here, the exact keyword arguments to pass
depend on each module and you'll need to refer to the ansible modules
documentation (e.g
https://docs.ansible.com/ansible/latest/modules/apt_module.html).
Currently, top-level keywords (e.g register, loop aren't supported).


Using a yaml playbook
---------------------

In addition to run custom command on nodes, |enoslib| can trigger predefined
playbook stored in your filesystem. This let you to use Ansible DSL to describe
your tasks or launch reusable playbook.

Let's consider the following script:

.. literalinclude:: ansible-integration/run_ansible.py
   :language: python
   :linenos:
   :emphasize-lines: 28

And the corresponding minimal playbook ``site.yml``:

.. literalinclude:: ansible-integration/site.yml
   :language: yaml
   :linenos:



What you should see at the end is:

.. code-block:: bash

    PLAY [This is a play] ******************************************************

    TASK [Gathering Facts] *****************************************************
    ok: [enos-0]
    ok: [enos-1]

    TASK [One task] ************************************************************
    ok: [enos-0] => {
        "msg": "I'm running on enos-0"
    }
    ok: [enos-1] => {
        "msg": "I'm running on enos-1"
    }

    PLAY RECAP *****************************************************************
    enos-0                     : ok=2    changed=0    unreachable=0    failed=0
    enos-1                     : ok=2    changed=0    unreachable=0    failed=0


What's next ?
=============

If you aren't familiar with Ansible, we encourage you to go through the `Ansible
documentation <https://docs.ansible.com/ansible/latest/index.html>`_, write your own playbooks, or integrate one existing from
`ansible galaxy <https://galaxy.ansible.com/>`_.
