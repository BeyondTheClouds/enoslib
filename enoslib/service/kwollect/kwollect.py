import time
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from enoslib.infra.enos_g5k import g5k_api_utils
from enoslib.infra.utils import mk_pools
from enoslib.objects import Host

from ..service import Service


class Kwollect(Service):
    def __init__(
        self,
        nodes: Iterable[Host],
    ):
        """Collect environmental metrics from the Grid'5000 Kwollect service

        To use this service, you must first call start() and stop() to
        define the time range for which you want to retrieve metrics.
        Alternatively, you can use this service as a context manager.

        Then, use get_metrics() to fetch metrics for further processing,
        or backup() to store the raw data.

        Some metrics are not available by default and require a specific
        job type, see https://www.grid5000.fr/w/Monitoring_Using_Kwollect

        Args:
            nodes: list of :py:class:`enoslib.Host` for which to collect metrics


        Examples:

            .. literalinclude:: examples/kwollect.py
                :language: python
                :linenos:

        """
        self.start_time: Optional[float] = None
        self.stop_time: Optional[float] = None
        self.nodes: List[Host] = list(nodes)
        self.deployed = False

    def deploy(self):
        """Validate that nodes are usable with kwollect (allows to fail early)"""
        # Basic check if all nodes are G5K nodes
        if not all(node.address.endswith(".grid5000.fr") for node in self.nodes):
            raise ValueError("Kwollect service only works on Grid'5000 nodes")
        self.deployed = True

    def start(self, start_time: Optional[float] = None):
        """Define the start time for metric collection.

        By default, the current time is used.  Make sure your clock is synchronised.

        Args:
            start_time: optional start time override, expressed as a Unix timestamp
        """
        # Just to make sure people don't forget to deploy(), in case we do
        # important stuff there one day
        if not self.deployed:
            raise ValueError("Method deploy() should be called first")
        # Prevent resetting the start timestamp by mistake
        if self.start_time is not None:
            raise ValueError("Method start() can only be called once")
        # Normal path
        if start_time is None:
            self.start_time = time.time()
        else:
            self.start_time = start_time

    def stop(self, stop_time: Optional[float] = None):
        """Define the stop time for metric collection.

        By default, the current time is used.  Make sure your clock is synchronised.

        Args:
            stop_time: optional stop time override, expressed as a Unix timestamp
        """
        # Just to make sure people don't forget to deploy(), in case we do
        # important stuff there one day
        if not self.deployed:
            raise ValueError("Method deploy() should be called first")
        # Prevent resetting the stop timestamp by mistake
        if self.stop_time is not None:
            raise ValueError("Method stop() can only be called once")
        # Normal path
        if stop_time is None:
            self.stop_time = time.time()
        else:
            self.stop_time = stop_time

    def __enter__(self):
        self.deploy()
        self.start()
        return self

    def __exit__(self, *args, **kwargs):
        self.stop()
        return False

    def available_metrics(
        self,
        nodes: Optional[Iterable[Host]] = None,
    ) -> Dict[str, List[Dict]]:
        """Returns the description of the metrics that are theoretically available
        for the given nodes.

        Args:
            nodes: optional list of nodes for which to retrieve metrics (default: all)

        Returns:
            dict giving a list of metrics description (as a dict) for each node.

        Example return value:
            {"gros-46.nancy.grid5000.fr": [
             {'description': 'Power consumption of node reported by wattmetre, in watt',
              'name': 'wattmetre_power_watt',
              'optional_period': 20,
              'period': 1000,
              'source': {'protocol': 'wattmetre'}},
             {'description': 'Default subset of metrics from Prometheus Node Exporter',
              'name': 'prom_node_load1',
              'optional_period': 15000,
              'period': 0,
              'source': {'port': 9100, 'protocol': 'prometheus'}},
             ...
            ]}
        """
        if nodes is None:
            nodes = self.nodes
        else:
            # Check that we are given a subset of the initial nodes
            if not set(nodes).issubset(self.nodes):
                raise ValueError("nodes must be a subset of self.nodes")
        return g5k_api_utils.available_kwollect_metrics(nodes)

    def backup(self, backup_dir: Optional[str] = None):
        """Backup the kwollect data.  One file is stored for each node.

        TODO: determine storage format.

        Args:
            backup_dir (str): path of the backup directory to use.
        """
        pass

    def get_metrics(
        self,
        metrics: Optional[List[str]] = None,
        nodes: Optional[Iterable[Host]] = None,
        summary: bool = False,
    ) -> Dict[str, List[Dict]]:
        """Retrieve metrics from Kwollect

        By default, all available metrics on all hosts are retrieved.  To
        speed up metrics retrieval, it is possible to filter on a subset
        of metrics and/or a subset of hosts.

        Args:
            metrics: optional list of metrics to retrieve (default: all)
            nodes: optional list of nodes for which to retrieve metrics (default: all)
            summary: whether to retrieve summarized metrics (default: False)

        Returns:
            dict giving a list of data points for each node.  The list is
            sorted in chronological order, but all metrics are intertwined.
            Each data point is a dictionary.

        Example:
        TODO
        """
        if self.start_time is None or self.stop_time is None:
            raise ValueError("Must call start() and stop()")
        if nodes is None:
            nodes = self.nodes
        else:
            # Check that we are given a subset of the initial nodes
            if not set(nodes).issubset(self.nodes):
                raise ValueError("nodes must be a subset of initial nodes")
        gk = g5k_api_utils.get_api_client()
        # Get involved G5K sites by building a list of (uid, site) pairs
        nodes_with_site = [host.address.split(".")[0:2] for host in nodes]
        # Group metrics by node
        metrics_by_node = defaultdict(list)
        # Call kwollect for each site (simple loop for now)
        # TODO: parallelize the loop
        for site, subnodes in mk_pools(
            nodes_with_site, lambda uid_site: uid_site[1]
        ).items():
            # Call kwollect
            kwargs = {
                "nodes": ",".join([uid for (uid, _) in subnodes]),
                "start_time": self.start_time,
                "end_time": self.stop_time,
                "summary": summary,
            }
            if metrics:
                kwargs["metrics"] = ",".join(metrics)
            # TODO: stream the result
            results = gk.sites[site].metrics.list(**kwargs)
            # Split result by node
            for res in results:
                metric = res.to_dict()
                node = "{}.{}.grid5000.fr".format(metric["device_id"], site)
                metrics_by_node[node].append(metric)
        return dict(metrics_by_node)
