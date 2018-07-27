# 1.7.0 (unreleased)

* TODO

# 1.6.0

* G5K: add subnet support
* An enostask can now returns a value
* Openstack/Chameleon: support region name
* Openstack/Chameleon: support for extra prefix for the resources
* Chameleon: use config lease name

# 1.5.0

* python3 compatibility
* Confirm with predictable NIC names on g5k

# 1.4.0

* Fix the autodoc generation
* Document the cookiecutter generation
* Default to debian9 for g5k

# 1.3.0

* Change setup format
* Move chameleon dependencies to extra_require

# 1.2.1

* Drop validation of the bandwitdh
* Add missing host file

# 1.2.0

* Add reset network


# 0.0.6 

* add `min` keyword in machine descipriotn on for G5K

# 0.0.5

* reservation is supported in g5k provider
* `expand_groups` is available in the api
* `get_cluster_interfaces` is available in the g5k api.

# 0.0.4

* Exclude not involved machines from the tc.yml run
* Take force_deploy in g5k provider
* Wait ssh to be ready when `check_network=True` in `generate_inventory`
* Add start/end enostask logging

# 0.0.3

* Add static provider
* Add OpenStack provider (and chameleon derivatives)
* Add `provider_conf` validation
* Rearchitect providers
* Add dummy functionnal tests
* Add network emulation

# 0.0.2 

* Add fake interface creation option un check_network
* Encapsulate check_network in generate_inventory
* Add automatic discovery of network interfaces names/roles
* Add vagrant/g5k provider

# 0.0.1

* Initial version
