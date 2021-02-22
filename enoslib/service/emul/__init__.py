"""
This module exposes different ways of doing network emulation [#e1]_ based on
``tc`` [#e2]_ of the ``iproute2`` tool and use ``netem`` [#e3]_ as cornerstone.

Different kinds of network topologies can be built and different level of
abstractions can be used.

At the network device interface level (lowest level for now) you can use
:py:func:`enoslib.service.emul.netem.netem` to set inbound and/or outbound
limitation on arbitrary network interfaces of your nodes. Nodes can be seen
as the vertices of a star topology where the center is the core of the
network. For instance the higher the latency on a node is, the further it is
from the core of the network.

The above prevent you to set heterogeneous limitations *ie* based on the
packets destinations. The function
:py:func:`enoslib.service.emul.htb.netem_htb` enforces Hierarhical Token
Bucket [#4]_ on your nodes. This lets you modelize a n-simplex topology where
the vertices represent your nodes and the edges the limitations.

Working at the device interface level provides you with great flexibility,
however this comes at the cost of being very explicit. For instance you must
know in advance the device names, the IP target... From a higher perpsective
two Services, working at the ``role`` level are provided. The services will
infer everything for you (device names, target IPs) based on high level
parameters. Of course, those services are using internally the above
function.

- :py:class:`enoslib.service.emul.netem.Netem` will enforce fully
  homogeneous network limitations -- think about a regular n-simplex where
  every vertex is at the same distance of the others.

- :py:class:`enoslib.service.emul.htb.NetemHTB` will enforce heterogeneous
  network limitations based on the role names. In this case the n-simplex is
  not regular in the general case.


.. note::

  Requirements:

    - ``ifb`` module loaded on the remote hosts for ``Netem`` service and
      `netem` function.
    - ``tc`` tool available (install ``iproute2`` package on debian based
      distribution)

.. topic:: Links:

    .. [#e1] https://en.wikipedia.org/wiki/Network_emulation
    .. [#e2] https://www.lartc.org/lartc.html
    .. [#e3] https://wiki.linuxfoundation.org/networking/netem
    .. [#e4] https://tldp.org/HOWTO/Traffic-Control-HOWTO/classful-qdiscs.html
"""
pass
