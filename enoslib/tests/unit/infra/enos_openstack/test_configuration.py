import jsonschema

from enoslib.infra.enos_openstack.configuration import Configuration
import enoslib.infra.enos_openstack.constants as constants
from ... import EnosTest


class TestConfiguration(EnosTest):

    def test_from_dictionnary_minimal(self):
        d = {
            "key_name": "test_key",
            "user": "test_user",
            "image": "test_image",
            "resources": {
                "machines": [],
                "networks": []
            }
        }
        conf = Configuration.from_dictionnary(d)
        self.assertEqual(constants.DEFAULT_ALLOCATION_POOL, conf.allocation_pool)
        self.assertEqual(constants.DEFAULT_CONFIGURE_NETWORK, conf.configure_network)

    def test_from_dictionnary_missing_keys(self):
        d = {
            "resources": {
                "machines": [],
                "networks": []
            }
        }
        with self.assertRaises(jsonschema.exceptions.ValidationError) as _:
            Configuration.from_dictionnary(d)


    def test_from_dictionnary(self):
        d = {
            "key_name": "test_key",
            "user": "test_user",
            "image": "test_image",
            "resources": {
                "machines": [{"roles": ["r1"], "flavour": "m1.tiny", "number": 1}],
                "networks": ["api"]
            }
        }
        conf = Configuration.from_dictionnary(d)
        self.assertEqual("test_key", conf.key_name)
        self.assertEqual("test_image", conf.image)
