"""
A monitoring stack is part of the observability tools that the experimenter
may need [#m1]_.

|enoslib| provides two monitoring stacks out of the box:

- Telegraf [#m2]_ /InfluxDB [#m3]_ /Grafana [#m4]_ (TIG) stack. This stack
  follows a push model where Telegraf agents are continuously a pushing metrics
  the InfluxDB collector. Grafana is used as a dashboard for visualizing
  the metrics.

- Telegraf/Promotheus [#m5]_ /Grafana (TPG) stack. This stack follows a pull model
  where the Prometheus collector are polling the Telegraf agents for new
  metrics. For instance, this model allows to overcome a limitation when the
  deployment spans Grid'5000 and FIT/IOTlab platform.

Note that the Telegraf agent are also configured to expose NVidia GPU metrics if
an NVidia GPU is detected and if the nvidia container toolkit is found
(installed with the :py:class:`~enoslib.service.docker.docker.Docker` service or
by you own mean).

.. topic:: links

    .. [#m1] https://sre.google/sre-book/monitoring-distributed-systems/
    .. [#m2] https://www.influxdata.com/time-series-platform/telegraf/
    .. [#m3] https://www.influxdata.com/products/influxdb/
    .. [#m4] https://grafana.com/
    .. [#m5] https://prometheus.io/
"""
pass
