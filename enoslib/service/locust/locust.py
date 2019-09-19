import os

from enoslib.api import play_on, run_ansible
from ..service import Service

CURRENT_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))

class Locust(Service):
    def __init__(self, master={}, agents={}, network=None, reportingDB=None, **kwargs):
        """Deploy a distributed Locust (see locust.io)

        This aims at deploying a distributed locust for load testing. Locust
        can be deployed either with its web interface or headless. This module
        also write a targeted_hosts.toml file (in /tmp) containing the addresses of
        targeted hosts (for load testing) and a reporting databases (can 
        be used with locust hook to send metrics to a databases such as influxDB)

        Please note that this module assume that `discover_network` has been run before

        Args:
            master (list): list of :py:class:`enoslib.Host` where the
                              master will be installed
            agents (list): list of :py:class:`enoslib.Host` where the slave will
                          be installed
            network (str): network role on which master, agents and targeted hosts
                            are deployed
            reportingDB (list): list of :py:class:`enoslib.Host`. Their IP addresse
                            (on specified network) will be written in /tmp/targeted_hosts.toml
                            at run.
        
        Examples:

            .. literalinclude:: examples/locust.py
                :language: python
                :linenos:
        """
        self.master = master
        self.agents = agents
        self.network = network
        self.reportingDB = reportingDB
        self.roles = {}
        self.roles.update(master=self.master, agent=self.agents)

        self.master_ip = self.master[0].extra[self.network + "_ip"]

    def deploy(self):
        """Install Locust on master and agent hosts"""
        with play_on(pattern_hosts="all", roles=self.roles) as p:
            p.apt(
                display_name="Installing python-setuptools",
                name="python-pip",
                state="present",
                update_cache=True,
            )
            p.pip(display_name="Installing Locust", name="locustio")
    
    def destroy(self):
        """
        Stop locust
        """
        with play_on(pattern_hosts="all", roles=self.roles) as p:
            p.shell(
                "pkill locust",
                display_name="Running locust (%s) on master..."%(file_name)
            )
    
    def run_with_ui(self, expe_dir, file_name, port="8089", targeted_hosts=None):
        """Run locust with its web user interface.

        Args:
            expe_dir (string): path (relative or absolute) to the experiment directory
            file_name (string): path (relative or absolute) to the main locustfile
            port (string): port for locust web interface 
            targeted_hosts (list): list of :py:class:`enoslib.Host`. Their IP addresse
                            (on specified network) will be written in /tmp/targeted_hosts.toml
                            at run.
        """
        self.__copy_experiment(expe_dir, file_name)
        self.__write_targeted_hosts_file(targeted_hosts if targeted_hosts else self.roles)
        with play_on(pattern_hosts="master", roles=self.roles) as p:
            p.shell(
                "nohup locust -f /tmp/%s --master --host=%s -P %s --logfile=/tmp/locust.log &"%(file_name, self.master_ip, port),
                display_name="Running locust (%s) on master..."%(file_name)
            )

        with play_on(pattern_hosts="agent", roles=self.roles) as p:
            p.shell(
                "nohup locust -f /tmp/%s --slave --master-host=%s --host=%s --logfile=/tmp/locust.log &"%(file_name, self.master_ip, self.master_ip),
                display_name="Running locust (%s) on agents (master at %s)..."%(file_name, self.master_ip)
            )
  
    def run_headless(self, expe_dir, file_name, nb_clients, hatch_rate, time, targeted_hosts=None):
        """Run locust headless (see https://docs.locust.io/en/stable/running-locust-without-web-ui.html)
        
        Args:
            expe_dir (string): path (relative or absolute) to the experiment directory
            file_name (string): path (relative or absolute) to the main locustfile
            nb_clients (int): total number of clients to spawn
            hatch_rate (int): number of clients to spawn per second
            time (string): time of the experiment
            targeted_hosts (list): list of :py:class:`enoslib.Host`. Their IP addresse
                            (on specified network) will be written in /tmp/targeted_hosts.toml
                            at run.
        """
        
        self.__copy_experiment(expe_dir, file_name)
        self.__write_targeted_hosts_file(targeted_hosts if targeted_hosts else self.roles)
        with play_on(pattern_hosts="master", roles=self.roles) as p:
            p.shell(
                "nohup locust -f /tmp/%s --master --host=%s --logfile=/tmp/locust.log --no-web -c %s -r %s --run-time %s --expect-slaves 2 &"%(file_name, self.master_ip, nb_clients, hatch_rate, time),
                display_name="Running locust (%s) on master..."%(file_name)
            )

        with play_on(pattern_hosts="agent", roles=self.roles) as p:
            p.shell(
                "nohup locust -f /tmp/%s --slave --master-host=%s --host=%s --logfile=/tmp/locust.log &"%(file_name, self.master_ip, self.master_ip),
                display_name="Running locust (%s) on agents (master at %s)..."%(file_name, self.master_ip)
            )

    def __generate_hosts_list(self, hosts):
        hosts_list = []
        for host in hosts:
            hosts_list.append(host.extra['%s_ip'%(self.network)])
        return hosts_list

    def __copy_experiment(self, expe_dir, file_name):
        src_dir = os.path.abspath(expe_dir)
        src_dir_name = os.path.basename(os.path.normpath(src_dir))

        run_ansible([os.path.join(CURRENT_PATH, "playbooks", "copy_bench.yml")], 
            roles={'master': self.master, 'agent': self.agents},
            extra_vars={'src_dir': src_dir, 'dest_dir': '/tmp/'})

        with play_on(pattern_hosts="all", roles=self.roles) as p:
            if os.path.exists("%s/requirements.txt"%(src_dir)):
                p.shell(
                    "pip3 install -r /tmp/%s/requirements.txt"%(src_dir_name),
                    display_name="Installing python deps"
                )

    def __write_targeted_hosts_file(self, targeted_hosts):
        with play_on(pattern_hosts="agent", roles=self.roles) as p:
            if self.reportingDB is not None:
                p.set_fact(reportingDB_addresses=self.__generate_hosts_list(self.reportingDB))
            p.set_fact(target_addresses=self.__generate_hosts_list(targeted_hosts))
            p.template(
                src="%s/templates/targeted_hosts.toml.j2"%(os.path.join(CURRENT_PATH)),
                dest="/tmp/targeted_hosts.toml",
                mode="u=rwx,g=rwx,o=rwx"
            )