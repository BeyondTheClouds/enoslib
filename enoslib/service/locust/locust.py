from pathlib import Path
import os
import time
from typing import Dict, Iterable, List, Optional

from enoslib.api import __python3__, actions
from enoslib.html import (
    dict_to_html_foldable_sections,
    html_to_foldable_section,
    html_from_sections,
    repr_html_check,
)
from enoslib.objects import Host, Network, Roles
from enoslib.utils import get_address

from ..service import Service
from ..utils import _set_dir

CURRENT_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
LOCAL_OUTPUT_DIR = Path("__enoslib_locust__")


class Locust(Service):

    # remove from the _repr_html everything that's not relevant nor supported yet
    _REPR_HTML_EXCLUDE = ["master", "workers", "networks", "priors"]

    def __init__(
        self,
        # deployment options
        master: Optional[Host] = None,
        workers: Optional[Iterable[Host]] = None,
        networks: Optional[Iterable[Network]] = None,
        worker_density: int = 1,
        # runtime options
        local_expe_dir: str = ".",
        locustfile: str = "locustfile.py",
        users: int = 1,
        spawn_rate: int = 1,
        run_time: int = 60,
        environment: Optional[Dict] = None,
        # orchestration options
        remote_working_dir: str = "/builds/locust",
        backup_dir: Optional[Path] = None,
        priors: List[actions] = [__python3__],
        extra_vars: Dict = None,
    ):
        """Deploy a distributed Locust (see locust.io)

        This aims at deploying a distributed locust for load testing.
        The Locust service has two modes of operations:

        - Web UI based:
        let the user to interact graphically with the benchmark
        (see :py:meth:`~enoslib.service.locust.locust.Locust.run_with_ui`)

        - Headless:
        ideal when load testing is part of a batch script.
        (see :py:meth:`~enoslib.service.locust.locust.Locust.run_headless`)
        By default calling
        :py:meth:`~enoslib.service.locust.locust.Locust.deploy` will
        deploy locust in headless mode (which is what you want in the
        general case).

        Please note that this module assume that
        :py:func:`~enoslib.api.sync_info` has been run before to allow advanced
        network filtering for worker/master communication.

        Args:
            master: :py:class:`~enoslib.objects.Host` where the
                    master will be installed
            workers: list of :py:class:`~enoslib.objects.Host` where the workers will
                    be installed
            worker_density: number of worker per node to start
                (max 1 per CPU core seems reasonable)
            networks: network role on which master, agents and targeted hosts
                     are deployed
            local_expe_dir: path to local directory containing all your Locust code.
                This will be copied on the remote machines.
            locustfile: main locust entry point file (usually locusfile.py)
            users: number of users to spawn
            spawn_rate: rate of spawning: number of new users per seconds.
            run_time: duration of the benchmark
            environment: Environment variables to make available to the remote
                locust script.  backup_dir: local directory where the backup
                will be performed

        Examples:

            .. literalinclude:: examples/locust.py
                :language: python
                :linenos:

            With the following ``expe/locustfile.py``:

            .. literalinclude:: examples/expe/locustfile.py
                :language: python
                :linenos:
        """
        self.master = master
        assert self.master is not None

        self.workers = workers if workers is not None else []
        # create a separated working dir for each instance of the service
        self.bench_id = str(int(time.time()))
        self.remote_working_dir = os.path.join(remote_working_dir, self.bench_id)
        self.priors = priors
        self.roles = Roles()
        self.roles.update(master=[self.master], agent=self.workers)

        self.master_ip = get_address(self.master, networks=networks)

        # handle local backup_dir
        self.backup_dir = _set_dir(backup_dir, LOCAL_OUTPUT_DIR)

        # We force python3
        self.extra_vars = extra_vars if extra_vars is not None else {}

        # handle runtime options
        self.local_expe_dir = local_expe_dir
        self.locustfile = locustfile
        self.users = users
        self.spawn_rate = spawn_rate
        self.run_time = run_time
        self.worker_density = worker_density

        self.environment = environment
        if not environment:
            self.environment = {}

    def info(self):
        d = dict(self.__dict__)
        d.update(ui=f"{self.master_ip}:8089")
        return d

    @repr_html_check
    def _repr_html_(self, content_only=False):
        # This is an attempt to get a more generic representation for a service
        info = self.info()
        # the top level representation made of standard types (int, float,
        # str...)
        to_repr = {}
        # the nested representations of attributes (those resulting on a call to
        # _repr_html_)
        sections = []
        for k, v in info.items():
            if k in self._REPR_HTML_EXCLUDE:
                continue
            if hasattr(v, "_repr_html_"):
                sections.append(
                    html_to_foldable_section(k, v._repr_html_(content_only=True))
                )
            else:
                to_repr.update({k: v})
        to_repr["ui (if any)"] = to_repr.pop("ui")
        sections += [dict_to_html_foldable_sections(to_repr)]

        return html_from_sections(
            str(self.__class__), sections, content_only=content_only
        )

    def _prepare(self):
        """Installs the locust dependencies."""
        with actions(
            pattern_hosts="all",
            roles=self.roles,
            priors=self.priors,
            extra_vars=self.extra_vars,
        ) as p:
            p.pip(task_name="Installing Locust", name="locust")
            p.file(path=self.remote_working_dir, recurse="yes", state="directory")

    def deploy(self):
        """Install and run locust on the nodes in headless mode."""
        self._prepare()
        self.run_headless()

    def destroy(self):
        """Stop locust."""
        with actions(
            pattern_hosts="all", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            p.shell("if pgrep locust; then pkill locust; fi")

    def backup(self, backup_dir: Optional[Path] = None):
        """Backup the locust files.

        We backup the remote working dir of the master.
        """
        _backup_dir = _set_dir(backup_dir, self.backup_dir)
        with actions(roles=self.roles) as a:
            a.archive(path=self.remote_working_dir, dest=f"/tmp/{self.bench_id}.tar.gz")
            a.fetch(src=f"/tmp/{self.bench_id}.tar.gz", dest=str(_backup_dir))

    def run_ui(
        self,
    ):
        """Run locust with its web user interface.

        Beware this will start a new Locust cluster.
        """

        # remove dangling execution
        self.destroy()
        self._prepare()
        if self.environment is None:
            environment = {}
        locustpath = self.__copy_experiment(self.local_expe_dir, self.locustfile)
        with actions(
            pattern_hosts="master", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            p.shell(
                (
                    "nohup locust "
                    f"-f {locustpath} "
                    "--master "
                    f"--host={self.master_ip} "
                    "--csv enoslib "
                    "--csv-full-history "
                    f"--logfile={self.remote_working_dir}/locust-master.log &"
                ),
                environment=environment,
                task_name="Running locust (%s) on master..." % (locustpath),
            )

        with actions(
            pattern_hosts="agent", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            for i in range(self.worker_density):
                p.shell(
                    (
                        "nohup locust "
                        f"-f {locustpath} "
                        "--worker "
                        f"--master-host={self.master_ip} "
                        f"--logfile={self.remote_working_dir}/locust-worker-{i}.log &"
                    ),
                    environment=environment,
                    chdir=self.remote_working_dir,
                    task_name=(
                        f"Running({locustpath}) on agents"
                        f"(master at {self.master_ip})..."
                    ),
                )

    def run_headless(self):
        """Run locust headless

        see https://docs.locust.io/en/stable/running-locust-without-web-ui.html
        """

        environment = dict(**self.environment)
        locustpath = self.__copy_experiment(self.local_expe_dir, self.locustfile)
        workers = len(self.roles["agent"]) * self.worker_density
        with actions(
            pattern_hosts="master", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            cmd = (
                "nohup locust "
                f"-f {locustpath} "
                "--master "
                "--logfile=/tmp/locust.log "
                "--headless "
                f"--expect-workers {workers} "
                f"--users {self.users} "
                f"--spawn-rate {self.spawn_rate} "
                f"--run-time {str(self.run_time)}s "
                "--csv enoslib "
                f"--logfile={self.remote_working_dir}/locust-master.log &"
            )
            p.shell(
                cmd,
                environment=environment,
                chdir=self.remote_working_dir,
                task_name="Running locust (%s) on master..." % (self.locustfile),
            )
            # record the exact master command
            p.copy(dest=f"{self.remote_working_dir}/cmd", content=cmd)

        with actions(
            pattern_hosts="agent", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            for i in range(self.worker_density):
                worker_local_id = f"locust-worker-{i}"
                environment.update(LOCUST_WORKER_LOCAL_ID=worker_local_id)
                p.shell(
                    (
                        "nohup locust "
                        f"-f {locustpath} "
                        "--worker "
                        f"--master-host={self.master_ip} "
                        f"--logfile={self.remote_working_dir}/{worker_local_id}.log &"
                    ),
                    environment=environment,
                    task_name=(
                        f"Running locust ({locustpath})"
                        f"on agents (master at {self.master_ip})..."
                    ),
                )
        with actions(roles=self.master, extra_vars=self.extra_vars) as p:
            # wait for the communication port between master and workers is closed
            # don't spam the master so sleeping 5 sec between each check
            p.wait_for(
                host=self.master_ip,
                port=5557,
                state="stopped",
                timeout=2 * self.run_time,
                sleep=5,
                task_name="Waiting benchmark completion...",
            )

    def __copy_experiment(self, expe_dir: str, locustfile: str):
        src_dir = os.path.join(os.path.abspath(expe_dir), "")
        remote_dir = os.path.join(self.remote_working_dir, expe_dir)
        with actions(
            pattern_hosts="all", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            p.copy(
                src=src_dir,
                dest=remote_dir,
                mode="u=rw,g=r,o=r",
                task_name="Copying the experiment directory into each hosts",
            )
            if os.path.exists(os.path.join(src_dir, "requirements.txt")):
                p.pip(
                    requirements=os.path.join(remote_dir, "requirements.txt"),
                    task_name="Installing python deps",
                )
        locustpath = os.path.join(remote_dir, locustfile)
        return locustpath
