from typing import List, Tuple

from enoslib.tests.unit import EnosTest
from enoslib.utils import generate_ssh_option_gateway


class TestSSHGateways(EnosTest):
    def test_empty_gateways(self):
        args: List[Tuple[str, None, None]] = []
        result = generate_ssh_option_gateway(args)
        self.assertEqual(
            "",
            result,
        )
        args = [("", None, None)]
        result = generate_ssh_option_gateway(args)
        self.assertEqual(
            "",
            result,
        )

    def test_single_gateway(self):
        args = [("gw", None, None)]
        result = generate_ssh_option_gateway(args)
        self.assertEqual(
            '-o ProxyCommand="ssh -W %h:%p -o StrictHostKeyChecking=no '
            '-o UserKnownHostsFile=/dev/null gw"',
            result,
        )

    def test_single_gateway_with_user(self):
        args = [("gw", "gwuser", None)]
        result = generate_ssh_option_gateway(args)
        self.assertEqual(
            '-o ProxyCommand="ssh -W %h:%p -o StrictHostKeyChecking=no '
            '-o UserKnownHostsFile=/dev/null -l gwuser gw"',
            result,
        )

    def test_single_gateway_with_user_and_port(self):
        args = [("gw", "gwuser", 2222)]
        result = generate_ssh_option_gateway(args)
        self.assertEqual(
            '-o ProxyCommand="ssh -W %h:%p -o StrictHostKeyChecking=no '
            '-o UserKnownHostsFile=/dev/null -l gwuser -p 2222 gw"',
            result,
        )

    def test_double_gateways(self):
        args = [("gwA", None, None), ("gwB", None, None)]
        result = generate_ssh_option_gateway(args)
        self.assertEqual(
            '-o ProxyCommand="ssh -W %h:%p -o StrictHostKeyChecking=no '
            "-o UserKnownHostsFile=/dev/null -o ProxyCommand='ssh -W %%h:%%p "
            "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null gwA' gwB\"",
            result,
        )

    def test_double_gateways_with_users(self):
        args = [("gwA", "userA", None), ("gwB", "userB", None)]
        result = generate_ssh_option_gateway(args)
        self.assertEqual(
            '-o ProxyCommand="ssh -W %h:%p -o StrictHostKeyChecking=no '
            "-o UserKnownHostsFile=/dev/null -l userB -o ProxyCommand='ssh -W %%h:%%p "
            "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -l userA gwA' "
            'gwB"',
            result,
        )

    def test_double_gateways_with_users_and_ports(self):
        args = [("gwA", "userA", 5000), ("gwB", "userB", 6000)]
        result = generate_ssh_option_gateway(args)
        self.assertEqual(
            '-o ProxyCommand="ssh -W %h:%p -o StrictHostKeyChecking=no '
            "-o UserKnownHostsFile=/dev/null -l userB -p 6000 "
            "-o ProxyCommand='ssh -W %%h:%%p "
            "-o StrictHostKeyChecking=no "
            "-o UserKnownHostsFile=/dev/null -l userA -p 5000 gwA' "
            'gwB"',
            result,
        )
