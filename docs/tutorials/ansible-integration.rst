.. _integration-with-ansible:

Tutorial 4 - Integration with Ansible
=====================================

|enoslib| uses internally Ansible to perform some predefined tasks (e.g network
emulation). The APIs allowing this are exposed so that anyone can use them.
User can thus :

* run a command to a set of nodes
* or run a full playbook

These two actions require an inventory to be created. As seen in the previous
tutorial this is accomplished by the :py:func:`~enoslib.api.generate_inventory`
function.


Run a command on nodes
----------------------

Let's consider the following script :

.. literalinclude:: ansible-integration/run_command.py
   :language: python
   :linenos:
   :emphasize-lines: 34

- :py:func:`~enoslib.api.run_command` takes 3 parameters :

    - the host pattern (see 
      https://docs.ansible.com/ansible/latest/intro_patterns.html)

    - the actual command to run

    - the Ansible inventory

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

Run a playbook
--------------

In addition to run custom command on nodes, |enoslib| can trigger predefined
playbook. This let you to use Ansible DSL to describe your tasks or launch
reusable playbook.

Let's consider the following script:

.. literalinclude:: ansible-integration/run_ansible.py
   :language: python
   :linenos:
   :emphasize-lines: 30

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


What's next
-----------

If you aren't familiar with Ansible, we encourage you to go through the `Ansible
documentation <https://docs.ansible.com/ansible/latest/index.html>`_, write your own playbooks, or integrate one existing from
`ansible galaxy <https://galaxy.ansible.com/>`_.
