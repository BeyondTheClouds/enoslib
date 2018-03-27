from enoslib.api import (_build_ip_constraints,
                                   _expand_description,
                                   _generate_default_grp_constraints,
                                   _generate_actual_grp_constraints,
                                   _build_grp_constraints,
                                   _merge_constraints)
from enoslib.host import Host
from enoslib.tests.unit import EnosTest

class TestExpandDescription(EnosTest):

    def test_no_expansion(self):
        desc = {
            'src': 'grp1',
            'dst': 'grp2',
            'delay': 0,
            'rate': 0,
            'symetric': True
        }
        descs = _expand_description(desc)
        self.assertEquals(1, len(descs))
        self.assertDictEqual(desc, descs[0])

    def test_src_expansion(self):
        desc = {
            'src': 'grp[1-3]',
            'dst': 'grp4',
            'delay': 0,
            'rate': 0,
            'symetric': True
        }
        # checking cardinality : the cartesian product
        descs = _expand_description(desc)
        self.assertEquals(3, len(descs))

        # checking that expansion has been generated
        srcs = map(lambda d: d.pop('src'), descs)
        self.assertEquals(set(srcs), {'grp1', 'grp2', 'grp3'})

        # checking that the remaining is untouched
        desc.pop('src')
        for d in descs:
            self.assertDictEqual(desc, d)


    def test_dst_expansion(self):
        desc = {
            'src': 'grp4',
            'dst': 'grp[1-3]',
            'delay': 0,
            'rate': 0,
            'symetric': True
        }
        # checking cardinality : the cartesian product
        descs = _expand_description(desc)
        self.assertEquals(3, len(descs))

        # checking that expansion has been generated
        dsts = map(lambda d: d.pop('dst'), descs)
        self.assertEquals(set(dsts), {'grp1', 'grp2', 'grp3'})

        # checking that the remaining is untouched
        desc.pop('dst')
        for d in descs:
            self.assertDictEqual(desc, d)


    def test_both_expansion(self):
        desc = {
            'src': 'grp[1-3]',
            'dst': 'grp[4-6]',
            'delay': 0,
            'rate': 0,
            'symetric': True
        }
        # checking cardinality : the cartesian product
        descs = _expand_description(desc)
        self.assertEquals(9, len(descs))

        # checking that expansion has been generated
        dsts = map(lambda d: d.pop('dst'), descs)
        self.assertEquals(set(dsts), {'grp4', 'grp5', 'grp6'})
        # checking that expansion has been generated
        srcs = map(lambda d: d.pop('src'), descs)
        self.assertEquals(set(srcs), {'grp1', 'grp2', 'grp3'})

        # checking that the remaining is untouched
        desc.pop('dst')
        desc.pop('src')
        for d in descs:
            self.assertDictEqual(desc, d)

class TestGenerateDefaultGrpConstraints(EnosTest):

    def test_no_expansion(self):
        roles = {
                'grp1': [],
                'grp2': []
         }
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms'
        }
        descs = _generate_default_grp_constraints(roles, network_constraints)

        # Cartesian product is applied
        self.assertEquals(2, len(descs))

        # defaults are applied
        for d in descs:
            self.assertEquals('10mbit', d['rate'])
            self.assertEquals('10ms', d['delay'])

        # descs are symetrics
        self.assertEquals(descs[0]['src'], descs[1]['dst'])
        self.assertEquals(descs[0]['dst'], descs[1]['src'])


    def test_except_one_group(self):
        roles = {
                'grp1': [],
                'grp2': [],
                'grp3': [],
         }
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'except': ['grp1']
        }
        descs = _generate_default_grp_constraints(roles, network_constraints)
        # Cartesian product is applied but grp1 isn't taken
        self.assertEquals(2, len(descs))

        for d in descs:
            self.assertTrue('grp1' != d['src'])
            self.assertTrue('grp1' != d['dst'])


    def test_include_two_groups(self):
        roles = {
                'grp1': [],
                'grp2': [],
                'grp3': [],
         }
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'groups': ['grp2', 'grp3']
        }
        descs = _generate_default_grp_constraints(roles, network_constraints)

        # Cartesian product is applied but grp1 isn't taken
        self.assertEquals(2, len(descs))

        for d in descs:
            self.assertTrue('grp1' != d['src'])
            self.assertTrue('grp1' != d['dst'])

class TestGenerateActualGrpConstraints(EnosTest):

    def test_no_expansion_no_symetric(self):
        constraints = [{
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '20mbit',
            'delay': '20ms'
            }]
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'constraints' : constraints
        }
        descs = _generate_actual_grp_constraints(network_constraints)

        self.assertEquals(1, len(descs))
        self.assertDictEqual(constraints[0], descs[0])


    def test_no_expansion_symetric(self):
        constraints = [{
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '20mbit',
            'delay': '20ms',
            'symetric': True
            }]
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'constraints' : constraints
        }
        descs = _generate_actual_grp_constraints(network_constraints)

        self.assertEquals(2, len(descs))

        # bw/rate are applied
        for d in descs:
            self.assertEquals('20mbit', d['rate'])
            self.assertEquals('20ms', d['delay'])

        # descs are symetrics
        self.assertEquals(descs[0]['src'], descs[1]['dst'])
        self.assertEquals(descs[0]['dst'], descs[1]['src'])

    def test_expansion_symetric(self):
        constraints = [{
            'src': 'grp[1-3]',
            'dst': 'grp[4-6]',
            'rate': '20mbit',
            'delay': '20ms',
            'symetric': True
            }]
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'constraints' : constraints
        }
        descs = _generate_actual_grp_constraints(network_constraints)

        self.assertEquals(3*3*2, len(descs))

        # bw/rate are applied
        for d in descs:
            self.assertEquals('20mbit', d['rate'])
            self.assertEquals('20ms', d['delay'])

    def test_expansion_no_symetric(self):
        constraints = [{
            'src': 'grp[1-3]',
            'dst': 'grp[4-6]',
            'rate': '20mbit',
            'delay': '20ms',
            }]
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'constraints' : constraints
        }
        descs = _generate_actual_grp_constraints(network_constraints)

        self.assertEquals(3*3, len(descs))

        # bw/rate are applied
        for d in descs:
            self.assertEquals('20mbit', d['rate'])
            self.assertEquals('20ms', d['delay'])

    def test_same_src_and_dest_defaults_embedded(self):
        constraints = [{
            'src': 'grp1',
            'dst': 'grp1',
            'rate': '20mbit',
            'delay': '20ms'
            }]
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'constraints' : constraints
        }
        descs = _generate_actual_grp_constraints(network_constraints)

        self.assertEquals(1, len(descs))
        self.assertDictEqual(constraints[0], descs[0])
        for d in descs:
            self.assertTrue('grp1' == d['src'])
            self.assertTrue('grp1' == d['dst'])

    def test_same_src_and_dest_without_defaults(self):
        roles = {
            'grp1': [Host('node1')],
            'grp2': [Host('node2')]
        }
        constraints = [{
            'src': 'grp1',
            'dst': 'grp1'
        }]
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'constraints': constraints
        }
        descs = _build_grp_constraints(roles, network_constraints)
        self.assertEquals(3, len(descs))
        # bw/rate are applied
        count_src_equals_dst = 0
        for d in descs:
            self.assertEquals('10mbit', d['rate'])
            self.assertEquals('10ms', d['delay'])
            if d['src'] == d['dst'] == 'grp1':
                count_src_equals_dst += 1
        self.assertEquals(1,count_src_equals_dst)


class TestMergeConstraints(EnosTest):

    def test__merge_constraints(self):
        constraint = {
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '10mbit',
            'delay': '10ms'
        }
        constraints = [constraint]
        override = {
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '20mbit',
            'delay': '20ms'
        }
        overrides = [override]
        _merge_constraints(constraints, overrides)
        self.assertDictEqual(override, constraints[0])

    def test__merge_constraints_default(self):
        constraint = {
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '10mbit',
            'delay': '10ms'
        }
        constraints = [constraint]
        override = {
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '20mbit',
        }
        overrides = [override]
        _merge_constraints(constraints, overrides)

        override.update({'delay': '10ms'})
        self.assertDictEqual(override, constraints[0])


class TestBuildIpConstraints(EnosTest):

    def test_build_ip_constraints(self):
        # role distribution
        rsc = {
            'grp1': [Host('node1')],
            'grp2': [Host('node2')]
        }
        # ips informations
        ips = {
            'node1': {
                'all_ipv4_addresses': ['ip11', 'ip12'],
                'devices': [{'device': 'eth0', 'active': True},{'device': 'eth1', 'active': True}]
             },
            'node2': {
                'all_ipv4_addresses': ['ip21', 'ip21'],
                'devices': [{'device': 'eth0', 'active': True},{'device': 'eth1', 'active': True}]
             }
        }
        # the constraints
        constraint = {
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '10mbit',
            'delay': '10ms',
            'loss': '0.1%'
        }
        constraints = [constraint]

        ips_with_tc = _build_ip_constraints(rsc, ips, constraints)
        # tc rules are applied on the source only
        self.assertTrue('tc' in ips_with_tc['node1'])
        tcs = ips_with_tc['node1']['tc']
        # one rule per dest ip and source device
        self.assertEquals(2*2, len(tcs))

if __name__ == '__main__':
    unittest.main()
