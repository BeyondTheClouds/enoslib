from abc import ABCMeta, abstractmethod
from typing import Any, Optional


class Provider:
    """Base class for the provider.

    Providers are components that are responsible for acquiring resources on
    existing testbeds. Concretely, a provider takes a declarative description
    of the expected resources as argument. It requests the resources on the
    corresponding testbed, and returns a set of hosts and networks labeled
    with their roles. In other words, providers help the experimenter deal
    with the variety of the APIs of testbeds.

    Some infrastructure is based on a reservation system (OAR, blazar ...).  In
    this case we defer to the decision to start the resource to the underlying
    scheduler. This scheduler will try to find an available ``start_time`` for
    our configuration in a near future if possible.

    In the above situation reservation in advance is possible and can be set in
    the corresponding configuration, using
    :py:meth:`~enoslib.infra.provider.Provider.set_reservation` or
    :py:meth:`~enoslib.infra.provider.Provider.init` with the ``start_time``
    parameter set.

    Example:

        Typical workflow:

            .. code-block:: python

                # craft a conf (provider specific)
                conf = Configuration() ...

                provider = Provider(conf)
                roles, networks = provider.init()

                # release resources
                provider.destroy()


        Using a context manager

            .. code-block:: python

                # craft a conf (provider specific)
                conf = Configuration() ...

                with provider(conf) as (roles, networks):
                    # do stuff with roles and networks
                    ...
                # Resources are automatically released at the end


    Args:
        provider_conf (BaseConfiguration): configuration of the provider.
            The configuration object is specific to each provider and must follow
            the provider's schema
    """

    __metaclass__ = ABCMeta

    def __init__(self, provider_conf, name: str = None):
        self.provider_conf = provider_conf.finalize()
        self.name = self.__class__.__name__ if name is None else name

    @abstractmethod
    def init(
        self,
        force_deploy: bool = False,
        start_time: Optional[int] = None,
        **kwargs: Any
    ):
        """Abstract. Provides resources and provisions the environment.

        This calls the underlying provider and provision resources (machines
        and networks).

        Args:
            force_deploy: boolean
                Indicates that the resources must be redeployed.
            start_time: timestamp (int)
                Date (UTC) when you want to have your resources ready.

        Returns:
            (roles, networks) tuple: roles is a dict whose key is a role and
            the value is the machines associated with this role. networks is
            the list of networks configured by the provider. see
            :py:class:`~enoslib.infra.enos_vagrant.provider.Enos_vagrant`
        """
        pass

    def async_init(self, **kwargs):
        """Partial init: secure the resources to the targeted infrastructure.

        This is primarily used internally by
        :py:class:`~enoslib.infra.providers.Providers` to get the resources from
        different platforms. As this method actually starts some real resources
        somewhere, errors may occur (e.g no more available resources, ...). It's
        up to the provider to indicate if the error is critical or not. For
        instance an :py:class:`~enoslib.errors.InvalidReservationTime` can be
        raised to indicate the Providers to retry later.

        Args:
            kwargs: keyword arguments.
                Fit those from
                :py:meth:`~enoslib.infra.provider.Provider.init`

        Raises:
            InvalidReservationTime:
                Resources can't be reserved at the specific time.
            InvalidReservationTooOld:
                The reservation time is in the past
            _: provider specific exception

        """
        self.init(**kwargs)

    def is_created(self) -> bool:
        """Is the provider already created."""
        return False

    @abstractmethod
    def destroy(self, wait=False, **kwargs):
        """Abstract. Destroy the resources used for the deployment."""
        pass

    def test_slot(self, start_time: int, end_time: int) -> bool:
        """Test a slot that starts at a given point in time.

        A slot is given by a start_time, a duration and an amount of resources.
        The two latter are found in the internal configuration.

        Args:
            start_time: timestamp (seconds)
                Test for a possible slot that starts at start_time (UTC)
            end_time: timestamp (seconds)
                How much time in the future we should look for possible reservation.
                This is used on some platform to know how much time in the
                future we look in the planning data. Timestamp is based on UTC.

        Returns:
            True iff the slot is available
        """
        return True

    def set_reservation(self, timestamp: int):
        """Change the internal reservation date.

        Ignored on platform that aren't based on a reservation system.

        Args:
            timestamp: timestamp (seconds)
                The reservation date (UTC) as timestamp in seconds.
        """
        pass

    def __str__(self):
        return self.name

    def __enter__(self):
        return self.init()

    def __exit__(self, *args):
        self.destroy()

    @abstractmethod
    def offset_walltime(self, offset: int):
        """Offset the walltime.

        Increase or reduce the wanted walltime.  This does not change the
        walltime of an already created provider but only affects the walltime
        configured before the provider calls ~init~.

        Raises:
            NegativeWalltime: the walltime is negative
        """
        pass
