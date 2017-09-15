import unittest
from enoslib.host import Host
from enoslib.ansible_utils import _generate_inventory_string


class TestGenerateInventoryString(unittest.TestCase):
    def test_address(self):
        h = Host("1.2.3.4")
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'", _generate_inventory_string(h))

    def test_address_alias(self):
        h = Host("1.2.3.4", alias="alias")
        role = "test"
        self.assertEqual("alias ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'", _generate_inventory_string(h))


    def test_address_user(self):
        h = Host("1.2.3.4", user="foo")
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_user=foo ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'", _generate_inventory_string(h))

    def test_address_gateway(self):
        h = Host("1.2.3.4", extra={'gateway': '4.3.2.1'})
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand=\"ssh -W %h:%p -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null 4.3.2.1\"'", _generate_inventory_string(h))

    def test_address_gateway_same_user(self):
        h = Host("1.2.3.4", user="foo", extra={'gateway': '4.3.2.1'})
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_user=foo ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand=\"ssh -W %h:%p -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -l foo 4.3.2.1\"'", _generate_inventory_string(h))
