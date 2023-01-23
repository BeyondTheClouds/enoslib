from pathlib import Path
from tempfile import TemporaryDirectory

import enoslib as en
from enoslib.api import AsyncCommandResult, CommandResult
from enoslib.config import config_context

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
conf = en.StaticConf().from_dictionary(provider_conf)
provider = en.Static(conf)
roles, networks = provider.init()
en.generate_inventory(roles, networks, inventory, check_networks=True)

# testing the generated inventory
assert inventory_path.exists() and inventory_path.is_file()
assert "[all]\ntest_machine ansible_connection='local'" in inventory_path.read_text()
assert "[control]\n test_machine ansible_connection='local'"

# With an inventory
results = en.run_command(
    "echo tototiti", pattern_hosts="control", inventory_path=inventory
)
print(results)
# testing the results
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""

# With roles
result = en.run_command("echo tototiti", pattern_hosts="control", roles=roles)
print(result)
# testing the results
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""


# With roles and async
results = en.run_command("date", pattern_hosts="control", roles=roles, background=True)
print(results)
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], AsyncCommandResult)
assert result[0].ansible_job_id
assert result[0].results_file

# With run and hosts
results = en.run("echo tototiti", roles["control"])
print(results)
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""


# With run and hosts and async
results = en.run("date", roles["control"], background=True)
print(results)
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], AsyncCommandResult)
assert result[0].ansible_job_id
assert result[0].results_file

# interpolation
results = en.run("echo {{ msg }}", roles["control"], extra_vars=dict(msg="tototiti"))
print(results)
result = results.filter(host="test_machine", status="OK")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""

# dump results
# test it in temporary directory
with TemporaryDirectory() as tmp:
    dump_file = Path(tmp) / "run_command.out"
    with config_context(dump_results=dump_file):
        results = en.run("echo tototiti", roles["control"])
    import json

    assert dump_file.exists()
    assert len(json.loads(dump_file.read_text())) == 1

    # subsequent run creates a run_command.out.1 file
    dump_file = Path(tmp) / "run_command.out"
    with config_context(dump_results=dump_file):
        results = en.run("echo tototiti", roles["control"])

    new_dump_file = Path(f"{dump_file}.1")
    import json

    assert new_dump_file.exists()
    assert len(json.loads(new_dump_file.read_text())) == 1
