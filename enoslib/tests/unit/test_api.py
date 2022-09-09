from enoslib.errors import EnosUnreachableHostsError

from unittest import mock

from . import EnosTest
from enoslib.api import (
    CommandResult,
    actions,
    get_hosts,
    wait_for,
    STATUS_OK,
    Results,
)
from enoslib.objects import Host, Roles


class TestSSH(EnosTest):
    longMessage = True
    hosts = [Host("1.2.3.4")]
    env = {"resultdir": "foo/bar", "inventory": "foo/bar"}

    def test_wait_ssh_succeed(self):
        with mock.patch("enoslib.api.run_play", new_callable=mock.Mock()) as m:
            m.return_value = []
            self.assertIsNone(wait_for(self.env, interval=0))

    def test_wait_ssh_eventually_succeed(self):
        with mock.patch("enoslib.api.run_play", new_callable=mock.Mock()) as m:
            # fail 9 times
            effects = [EnosUnreachableHostsError(self.hosts) for i in range(1, 10)]
            # succeed on the last
            effects.append([])
            m.side_effect = effects
            self.assertIsNone(wait_for(self.env, retries=10, interval=0))

    def test_wait_ssh_fails(self):
        with self.assertRaisesRegex(Exception, "Maximum retries reached"), mock.patch(
            "enoslib.api.run_play", new_callable=mock.Mock()
        ) as m:
            # fail all the time
            m.side_effect = EnosUnreachableHostsError(self.hosts)
            wait_for(self.env, interval=0)


class TestPlayOn(EnosTest):
    def test_modules(self):
        p = actions(pattern_hosts="pattern")
        p.__exit__ = mock.MagicMock()
        a = p.__enter__()
        a.test_module(name="test", state="present")
        self.assertEqual(1, len(a._tasks))
        task = a._tasks[0]
        self.assertEqual({"name": "test", "state": "present"}, task["test_module"])

    def test_call_ansible(self):
        with mock.patch("enoslib.api.run_play") as m:
            with actions(pattern_hosts="pattern", roles=Roles()) as p:
                p.a()
            m.assert_called_once()


class TestGetHosts(EnosTest):
    def test_get_all(self):
        roles = {
            "client.1": [Host("1.2.3.4")],
            "client.2": [Host("2.2.3.4")],
            "server": [Host("3.2.3.4")],
        }
        hosts = get_hosts(roles)
        self.assertEqual(3, len(hosts))
        hosts = get_hosts(roles, pattern_hosts="client*")
        self.assertEqual(2, len(hosts))


class TestResultFiltering(EnosTest):
    def test_result_single(self):
        cr = CommandResult(host="host", task="task", status=STATUS_OK, payload={})

        # exact match
        self.assertTrue(cr.match(host="host"))

        # exact mismatch
        self.assertFalse(cr.match(host="plop"))

        with self.assertRaises(AttributeError):
            # non existent key
            self.assertTrue(cr.match(plop="host"))

        # 2 exact matches
        self.assertTrue(cr.match(host="host", task="task"))

        # 1 mismatch
        self.assertFalse(cr.match(host="plop", task="task"))

    def test_result_container(self):
        results = Results(
            [
                CommandResult(
                    host=f"host-{i}", task=f"task-{i}", status=STATUS_OK, payload={}
                )
                for i in range(10)
            ]
        )
        results.filter(host="host-3")
