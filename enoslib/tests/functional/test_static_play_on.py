import enoslib as en
from enoslib.api import CommandResult, AsyncCommandResult

from pathlib import Path


# Dummy functional test running inside a docker container

logging = en.init_logging()

provider_conf = {
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "address": "localhost",
                "alias": "test_machine",
                "extra": {"ansible_connection": "local"},
            }
        ],
        "networks": [
            {
                "roles": ["local"],
                "start": "172.17.0.0",
                "end": "172.17.255.255",
                "cidr": "172.17.0.0/16",
                "gateway": "172.17.0.1",
                "dns": "172.17.0.1",
            }
        ],
    }
}

inventory_path = Path.cwd() / "hosts"

# we still need str instead of pathlib.Path in enoslib.api functions that uses inventory
inventory = str(inventory_path)
conf = en.StaticConf.from_dictionary(provider_conf)
provider = en.Static(conf)
roles, networks = provider.init()
en.generate_inventory(roles, networks, inventory, check_networks=True)

# testing the generated inventory
assert inventory_path.exists() and inventory_path.is_file()
assert "[all]\ntest_machine ansible_connection='local'" in inventory_path.read_text()
assert "[control]\n test_machine ansible_connection='local'"

# from roles
with en.actions(roles=roles) as a:
    a.shell("echo tototiti")
    results = a.results
print(results)
# testing the results
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""

# from roles
with en.actions(roles=roles) as a:
    a.ansible.builtin.shell("echo tototiti")
    results = a.results
print(results)
# testing the results
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""


# from an inventory
with en.actions(inventory_path=inventory) as a:
    a.shell("echo tototiti")
    results = a.results
print(results)
# testing the results
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""


# async
with en.actions(pattern_hosts="all", roles=roles, background=True) as a:
    for i in range(10):
        a.shell("sleep 10")
    results = a.results

print(results)
assert len(results) == 10
for result in results:
    assert isinstance(result, AsyncCommandResult)
    assert result.ansible_job_id
    assert result.results_file
