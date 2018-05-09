Tutorial 0 - Quickstart
=======================

This tutorial will let you get started very quickly using |enoslib|. It will
show you how to bootstrap a new project and start working.

This includes:

* an example to work with the Vagrant and Grid'5000 provider
* a command line interface
* a set of `enostask` to orchestrate a minimal experience
* a minimal ansible code with the action `deploy`, `backup`, `destroy` actions
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



