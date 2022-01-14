import logging
from pathlib import Path

from enoslib.api import generate_inventory, run_command, run, CommandResult, AsyncCommandResult
from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_static.configuration import Configuration

# Dummy functionnal test running inside a docker container
logging.basicConfig(level=logging.DEBUG)


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
conf = Configuration.from_dictionnary(provider_conf)
provider = Static(conf)
roles, networks = provider.init()
generate_inventory(roles, networks, inventory, check_networks=True)

# testing the generated inventory
assert inventory_path.exists() and inventory_path.is_file()
assert "[all]\ntest_machine ansible_connection='local'" in inventory_path.read_text()
assert "[control]\n test_machine ansible_connection='local'"

# With an inventory
results = run_command("echo tototiti", pattern_hosts="control", inventory_path=inventory)
print(results)
# testing the results
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""

# With roles
result = run_command("echo tototiti", pattern_hosts="control", roles=roles)
print(result)
# testing the results
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""


# With roles and async
results = run_command("date", pattern_hosts="control", roles=roles, background=True)
print(results)
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], AsyncCommandResult)
assert result[0].ansible_job_id
assert result[0].results_file

# With run and hosts
results = run("echo tototiti", roles["control"])
print(results)
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""


# With run and hosts and async
results = run("date", roles["control"], background=True)
print(results)
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], AsyncCommandResult)
assert result[0].ansible_job_id
assert result[0].results_file