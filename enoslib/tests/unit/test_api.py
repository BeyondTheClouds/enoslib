import unittest
from enoslib.api import *
from enoslib.host import Host
import mock

class TestSSH(unittest.TestCase):
    longMessage = True
    hosts = [Host('1.2.3.4')]
    env = {'resultdir': 'foo/bar', 'inventory': 'foo/bar'}

    def test_wait_ssh_succeed(self):
        with mock.patch('enoslib.api.run_ansible',
                        new_callable=mock.Mock()) as m:
            m.return_value=None
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
            m.side_effect=EnosUnreachableHostsError(self.hosts)
            wait_ssh(self.env, interval=0)

