import unittest

import mock

from enoslib.api import *
from enoslib.host import Host

class TestSSH(unittest.TestCase):
    longMessage = True
    hosts = [Host('1.2.3.4')]
    env = {'resultdir': 'foo/bar', 'inventory': 'foo/bar'}

    def test_wait_ssh_succeed(self):
        with mock.patch('enoslib.api.run_ansible',
                        new_callable=mock.Mock()) as m:
            m.return_value = None
            self.assertIsNone(wait_ssh(self.env, interval=0))

    def test_wait_ssh_eventually_succeed(self):
        with mock.patch('enoslib.api.run_ansible',
                        new_callable=mock.Mock()) as m:
            effects = [EnosUnreachableHostsError(self.hosts)
                       for i in range(1, 10)]
            effects.append(None)
            m.side_effect = effects
            self.assertIsNone(wait_ssh(self.env, retries=10, interval=0))

    def test_wait_ssh_fails(self):
        with self.assertRaisesRegexp(Exception, 'Maximum retries reached'),\
             mock.patch('enoslib.api.run_ansible',
                        new_callable=mock.Mock()) as m:
            m.side_effect = EnosUnreachableHostsError(self.hosts)
            wait_ssh(self.env, interval=0)


class TestPlayOn(unittest.TestCase):

    def test_no_gather(self):
        p = play_on("pattern", gather_facts=False)
        p.__exit__ = mock.MagicMock()
        a = p.__enter__()
        self.assertEqual({}, p.prior)
        self.assertEqual([], p._tasks)

    def test_gather(self):
        p = play_on("pattern")
        p.__exit__ = mock.MagicMock()
        a = p.__enter__()
        g = {
            "hosts": "all",
            "tasks": [{
                "name": "Gathering Facts",
                "setup": {"gather_subset": "all"}
            }]
        }
        self.assertDictEqual(g, p.prior)

    def test_modules(self):
        p = play_on("pattern")
        p.__exit__ = mock.MagicMock()
        a = p.__enter__()
        a.test_module(name="test", state="present")
        self.assertEquals(1, len(a._tasks))
        task = a._tasks[0]
        self.assertEquals({"name": "test", "state": "present"},
                          task["test_module"])

    def test_call_ansible(self):
        with mock.patch('enoslib.api.run_ansible') as m:
            with play_on("pattern") as p:
                p.a()
            m.assert_called_once()
