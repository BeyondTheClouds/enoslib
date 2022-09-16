import jsonschema

from enoslib.infra.enos_openstack.configuration import Configuration
import enoslib.infra.enos_openstack.constants as constants
from ... import EnosTest


class TestConfiguration(EnosTest):
    def test_from_dictionary_minimal(self):
        d = {
            "key_name": "test_key",
            "user": "test_user",
            "image": "test_image",
            "rc_file": "test_rc_file",
            "resources": {"machines": [], "networks": []},
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual(constants.DEFAULT_ALLOCATION_POOL, conf.allocation_pool)
        self.assertEqual(constants.DEFAULT_CONFIGURE_NETWORK, conf.configure_network)

    def test_from_dictionary_missing_keys(self):
        d = {"resources": {"machines": [], "networks": []}}
        with self.assertRaises(jsonschema.exceptions.ValidationError) as _:
            Configuration.from_dictionary(d)

    def test_from_dictionary(self):
        d = {
            "key_name": "test_key",
            "user": "test_user",
            "image": "test_image",
            "rc_file": "rc_file",
            "resources": {
                "machines": [{"roles": ["r1"], "flavour": "m1.tiny", "number": 1}],
                "networks": ["api"],
            },
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual("test_key", conf.key_name)
        self.assertEqual("test_image", conf.image)
