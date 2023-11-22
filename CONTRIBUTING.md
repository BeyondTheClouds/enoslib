# Contributing

Contributing is available at [https://gitlab.inria.fr/discovery/enoslib](https://gitlab.inria.fr/discovery/enoslib)!

## Tools

## pre-commit

```sh
# install pre-commit
python -m pip install -u pre-commit
# install pre-commit hook
python -m pre_commit install

# useful command
python -m pre_commit run --all-files
```

## pytest

```sh
# simple pytest
python -m pytest path/to/file
```

## tox

```sh
python -m pip install tox
python -m tox

# unit tests (change python target if needed)
tox -e py310

#pylint
tox -e pylint

# typecheck
tox -e typecheck
```
