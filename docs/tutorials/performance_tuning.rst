.. _performance_tuning:

******************
Performance tuning
******************


This page is about tricks to speed up the deployment time.

- On Grid5000, use a dedicated node as the experiment manager instead of the
  local frontends

- Ansible

  - Use fact caching: https://docs.ansible.com/ansible/latest/user_guide/playbooks_variables.html#caching-facts
  - Tune the default ssh strategy:

    - pipelining: https://docs.ansible.com/ansible/latest/reference_appendices/config.html?highlight=pipelining#ansible-pipelining
    - forks: https://docs.ansible.com/ansible/latest/reference_appendices/config.html?highlight=pipelining#default-forks

  - Switch to another ssh strategy:

    - mitogen: https://networkgenomics.com/ansible/

- Build a preconfigured image (application specific)
