import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from enoslib.infra.enos_g5k import g5k_api_utils
from enoslib.infra.utils import mk_pools
from enoslib.objects import Host

from ..service import Service
from ..utils import _set_dir


class Kwollect(Service):
    def __init__(
        self,
        nodes: Iterable[Host],
    ):
        """Collect environmental metrics from the Grid'5000 Kwollect service

        This service must be called on Grid'5000 nodes.

        To fetch metrics from the service, you first have to call
        :py:meth:`~enoslib.service.kwollect.kwollect.Kwollect.start` and
        :py:meth:`~enoslib.service.kwollect.kwollect.Kwollect.stop` to
        define the time range for which you want to retrieve metrics.
        Alternatively, you can use this service as a context manager.

        Then, use
        :py:meth:`~enoslib.service.kwollect.kwollect.Kwollect.get_metrics`
        or
        :py:meth:`~enoslib.service.kwollect.kwollect.Kwollect.get_metrics_pandas`
        to fetch metrics for further processing, or
        :py:meth:`~enoslib.service.kwollect.kwollect.Kwollect.backup` to
        store the raw data locally.

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
        nodes_name = [node.address for node in nodes]
        return g5k_api_utils.available_kwollect_metrics(nodes_name)

    def backup(
        self,
        backup_dir: Optional[str] = None,
        metrics: Optional[List[str]] = None,
        nodes: Optional[Iterable[Host]] = None,
        summary: bool = False,
    ):
        """Backup the kwollect data in JSONL format (one JSON record per line).
        Data for each node is stored in separate files.

        Args:
            backup_dir (str): path of the backup directory to use.
            metrics: optional list of metrics to retrieve (default: all)
            nodes: optional list of nodes for which to retrieve metrics (default: all)
            summary: whether to retrieve summarized metrics (default: False)
        """
        # Default backup dir
        identifier = str(time.time_ns())
        default_dir = Path("enoslib_kwollect") / identifier
        # Create backup dir
        _backup_dir = _set_dir(backup_dir, default_dir, mkdir=True)
        # Get metrics data and group it by node
        data = self.get_metrics(metrics, nodes, summary)
        data_by_node = defaultdict(list)
        for site, subdata in data.items():
            for metric in subdata:
                node = "{}.{}.grid5000.fr".format(metric["device_id"], site)
                data_by_node[node].append(metric)
        # Write to files
        for node, values in data_by_node.items():
            # TODO: compress output
            filename = f"{node}.jsonl"
            with open(_backup_dir / filename, "w") as f:
                for value in values:
                    d = json.dumps(
                        value, indent=None, separators=(",", ":"), ensure_ascii=False
                    )
                    f.write(d)
                    f.write("\n")

    def get_metrics(
        self,
        metrics: Optional[List[str]] = None,
        nodes: Optional[Iterable[Host]] = None,
        summary: bool = False,
    ) -> Dict[str, List[Dict]]:
        """Retrieve metrics from Kwollect

        By default, all available metrics on all hosts are retrieved.  To
        speed up metrics retrieval, it is recommended to filter on a subset
        of metrics and/or a subset of hosts.

        Available metrics can be found with :py:meth:`~enoslib.service.kwollect.kwollect.Kwollect.available_metrics`
        or are listed here:
        https://www.grid5000.fr/w/Monitoring_Using_Kwollect#Metrics_available_in_Grid'5000

        Args:
            metrics: optional list of metrics to retrieve (default: all)
            nodes: optional list of nodes for which to retrieve metrics (default: all)
            summary: whether to retrieve summarized metrics (default: False)

        Returns:
            A list of data points for each site.  Each data point is a
            dictionary.  All data points are sorted in chronological
            order.

        Example:

        {"nantes": [
          {"timestamp": "2025-04-18T18:55:33.754307+02:00",
           "device_id": "ecotype-7",
           "metric_id": "bmc_node_power_watt",
           "value": 98,
           "labels": {}},
          {"timestamp": "2025-04-18T18:55:34.732712+02:00",
           "device_id": "ecotype-6",
           "metric_id": "network_ifacein_bytes_total",
           "value": 152601965318
           "labels": {"interface": "eth1", "_device_orig": ["ecotype-prod2-port-1_6"]}
          },
          ...
        ]}
        """  # noqa: E501
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
        data = dict()
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
            # Convert each Metric object to a dict
            data[site] = [r.to_dict() for r in results]
        return data

    def get_metrics_pandas(self, *args, **kwargs):
        """Same as
        :py:meth:`~enoslib.service.kwollect.kwollect.Kwollect.get_metrics`,
        but returns the result as a Pandas Dataframe.  Data from all sites
        is aggregated in the same Dataframe, with an additional "site"
        column.

        Returns:
            A Pandas Dataframe with all metrics data

        """
        import pandas

        raw_data = self.get_metrics(*args, **kwargs)
        dataframes = []
        for site, subdata in raw_data.items():
            df = pandas.DataFrame(subdata)
            df["site"] = site
            dataframes.append(df)
        # Merge all dataframes
        df_all = pandas.concat(dataframes)
        # Parse timestamps properly
        df_all["timestamp"] = pandas.to_datetime(df_all["timestamp"])
        return df_all
