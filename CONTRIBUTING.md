# Contributing

Contributing is available at [https://gitlab.inria.fr/discovery/enoslib](https://gitlab.inria.fr/discovery/enoslib)!

## Tools

### pre-commit

```sh
# install pre-commit
python -m pip install -u pre-commit
# install pre-commit hook
python -m pre_commit install

# useful command
python -m pre_commit run --all-files
```

### pytest

```sh
# simple pytest
python -m pytest path/to/file
```

### tox

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

## How to make a release

### 1. In-vivo tests launch

On GitLab UI :

- Go to the pipeline of the last commit in `main`
- Manually launch the `invivog5k-deb11` job
- When finished, launch the `invivog5k-deb12` job

### 2. Preparation of the release

Note : X_X_X represents the Major.Minor.Patch version numbers (e.g., 1_2_0), following standard software versioning conventions.

#### 2.1 Install the tools

```sh
pip install -U pip
pip install bump2version
```

#### 2.2 Update the changelog (to do in part 3)

Modify the `changelog.rst` file :
- Retrieve what's in "Unreleased" section
- Put it in a new section at the beggining of "Stable branch" one
    - Any uncommented feature or bugfix not present in the emptied "Unreleased" section and done since the last release must be filled in this section
    - Organize those features in categories
        - Tip : examples from previous releases may help you find inspiration
    - This section must start like this :
        ```rst
        .. _vX.X.X:

        X.X.X
        -------
        ```

- Commit your modifications :

```sh
git commit -am "Update changelog for vX.X.X"
```

### 3. Change the version and release

You now have the choice between two methods.

#### 3.1 With a dedicated branch (recommended)

Locally on your machine :

- Create a branch `dev/release_X_X_X` from `main` :

```sh
git checkout main
git pull
git checkout -b dev/release_X_X_X
```

- Modify the `changelog.rst` file according to part 2.2

- If necessary, modify the upper limit year in `docs/conf.py` in `copyright` variable

- Update the version using `bump2version` tool

    - Run the command according to the type of release you are making :
        ```sh
        bump2version patch --no-tag # or minor, or major
        ```
        - This will automatically :
            - change the version in configured files ;
            - commit the modifications.

- Then push :

```sh
git push -u origin dev/release_X_X_X
```

- Open a Merge Request, and merge it (select "Delete source branch").

- For the tag :

```sh
git checkout main
git pull
git tag vX.X.X
git push --tags
```

- This launches the packaging and documentation website deployment.
    - Check that everything went well with the pipeline for `package`, `publish` and `deploy` jobs

#### 3.2 Directly on main (quick & dirty)

Locally on your machine :

- Switch to the `main` branch :

```sh
git checkout main
git pull
```

- Modify the `changelog.rst` file according to part 2.2

- If necessary, modify the upper limit year in `docs/conf.py` in `copyright` variable

- Update the version using `bump2version` tool
    - Run the command according to the type of release you are making :
        ```sh
        bump2version patch # or minor, or major
        ```
        - This will automatically :
            - change the version in configured files ;
            - update the tag ;
            - commit the modifications.

- Eventually, push the modifications (for both files and tag) :

```sh
git push --follow-tags
```

- This launches the packaging and documentation website deployment.
    - Check that everything went well with the pipeline for `package`, `publish` and `deploy` jobs

#### 3.3 Troubleshooting : bad tag

If you messed up the tag (e.g., forgot to push something before tagging) :

```sh
git checkout main
git pull
git push --delete origin vX.X.X
git tag --delete vX.X.X

# Do some stuff

git tag vX.X.X
git push --follow-tags
```

### 4. Communication regarding the release

Don't hesitate to send a message on the [Town-square channel](https://framateam.org/enoslib/channels/town-square) of EnOSlib's Mattermost server to announce the release and sum up its content !
