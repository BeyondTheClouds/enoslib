from typing import Iterable

from collections import UserDict
from collections.abc import MutableSet


class ResourcesSet(MutableSet):
    """Wrapper around a Set exposing also some lists' operations.

    Items of the Set must be comparable and hashable.

    It's possible for instance to call ``append``, ``extend``, etc.  Indexing
    comes for instance with some caveats however: ``resource_set[0]`` will give
    you the first resource in the *alphabetical order* not the first inserted
    machine as you'd expect with a regular list.
    """

    def __init__(self, iterable: Iterable = None):
        self.data = set()
        if iterable:
            self.data = set(iterable)

    def __repr__(self):
        return self.data.__repr__()

    def __contains__(self, key):
        return key in self.data

    def __iter__(self):
        yield from self.data

    def __len__(self):
        return len(self.data)

    def add(self, value):
        self.data.add(value)

    def discard(self, value):
        if value in self.data:
            self.data.remove(value)

    # custom methods
    #
    def __isub__(self, other):
        # in place version
        if isinstance(other, ResourcesSet):
            other = other.data
        self.data -= set(other)
        return self

    def __sub__(self, other):
        if isinstance(other, ResourcesSet):
            return ResourcesSet(self.data.difference(other.data))
        return ResourcesSet(self.data.difference(other))

    # compatibility with some list method
    def __iadd__(self, other):
        if isinstance(other, ResourcesSet):
            other = other.data
        self.data |= set(other)
        return self

    def __add__(self, other):
        if isinstance(other, ResourcesSet):
            return ResourcesSet(self.data.union(other.data))
        return ResourcesSet(self.data.union(other))

    def extend(self, other):
        self += other
        return self

    def append(self, value):
        return self.add(value)

    def __radd__(self, other):
        # called I want to add
        # "something that doesn't know how to add with a UserSet"
        # and a UserSet (who knows how to be added with himself)
        # but here we expect a commutative operation so...
        return self + other

    def __getitem__(self, i):
        # sorting to ensure determinism
        sorted_data = sorted(list(self.data))
        if isinstance(i, slice):
            return ResourcesSet(elem for elem in sorted_data[i])
        else:
            return [elem for elem in sorted_data if elem == sorted_data[i]][0]


class RolesDict(UserDict):
    """RolesDict is a way to group resources of the same type together using tags.

    From the user perspective, a RolesDict's instance ``roles`` is a
    dictionary.  To retrieve all the corresponding machine with the tag ``tag``
    one can use `̀`roles[tag]``.

    The value associated with a tag behaves like a set (it's a
    py:class:`~enoslib.collections.ResourcesSet`). So classical set operations
    are possible, for instance ``roles[tag1] & roles[tag2]`` will give you back
    the set of resources that are both tagged with ``tag1`` and ``tag2``.

    This set also accepts some list operations (as it seems that users
    are more familiar with them). So it's possible to call ``append``,
    ``extend``, etc. Indexing comes with some caveats however:
    ``roles["tag"][0]`` will give you the first resource in the *alphabetical
    order* associated with the tag ``tag``(not the first inserted machine as
    you'd expect with a regular list).
    """

    inner = ResourcesSet

    # TODO XXX: should we deduplicate the object that we're adding on different
    # roles ?  For now it's up to the user to make sure to not push duplicated
    # object on the data structure

    def __missing__(self, key):
        return self.inner()

    def __setitem__(self, key, item):
        """This is also used when r = Roles(a=..., b=...)"""
        if not isinstance(item, self.inner):
            # in this case we create a new HostsView
            self.data[key] = self.inner(item)
        else:
            # assuming item is an Iterable[Host]
            self.data[key] = item

    def all(self) -> Iterable:
        all_hosts = self.inner()
        for hosts in self.values():
            all_hosts += hosts
        return all_hosts

    def __add__(self, other):
        result = RolesDict()
        for role, hosts in self.items():
            result[role] += hosts
        for role, hosts in other.items():
            result[role] += hosts
        return result

    def __iadd__(self, other):
        for role, hosts in other.items():
            self[role] += hosts
        return self

    def extend(self, roles):
        self += roles

    def add_one(self, elem, keys):
        for key in keys:
            self[key] += [elem]
