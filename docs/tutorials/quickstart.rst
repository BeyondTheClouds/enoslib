Tutorial 7 - Project bootstrap
==============================

EnOSlib project can be a single python file but sometimes it's better to
structure a bit more your experimental framework. In this direction, we're doing
our best to maintain a project template that you can use.

This includes:

* an example to work with the Vagrant and Grid'5000 provider
* a command line interface
* a set of `enostask` to orchestrate a minimal experience
* a minimal ansible code with the action `deploy`, `backup`, `destroy` actions
  (Ansible is located in dedicated files by default).
* third party tools like `sphinx` (documentation), `pytest` (unit tests), `tox`
  and a `travis` integration.


Bootstrap a new project
-----------------------

Install the latest Cookiecutter if you haven't installed it yet (this requires
Cookiecutter 1.4.0 or higher)::

    pip install -U cookiecutter

Generate an Enoslib project::

    cookiecutter https://github.com/msimonin/cookiecutter-enoslib.git

You'll be asked for some information::

    author [John Doe]: Matthieu Simonin
    project_name [Enoslib boilerplate]: my_project
    project_slug [my_project]:
    project_short_description [Boilerplate to bootstrap a new experimentation framework using Enoslib]:
    version [0.0.1]:
    project_url []: https://github.com/msimonin/my_project
    cli_name [my_project]: mp


Using the new project
---------------------

Within a virtualenv you can do::

    pip install -e .

and start using the cli (the cli name has been filled above)::

    mp --help

    Usage: mp [OPTIONS] COMMAND [ARGS]...

    Options:
      --help  Show this message and exit.

    Commands:
      backup     Backup the deployed environment
      deploy     Claim resources from a PROVIDER and configure...
      destroy    Destroy the deployed environment
      g5k        Claim resources on Grid'5000 (frontend).
      inventory  Generate the Ansible inventory [after g5k or...
      prepare    Configure available resources [after deploy,...
      vagrant    Claim resources on vagrant (localhost).

