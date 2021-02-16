import unittest
from mt5_correlation.config import Config


class TestConfig(unittest.TestCase):
    def test_load_and_get(self):
        config = Config()
        config.load("testconfig.yaml")
        val121 = config.get('test1.test1_2.val1_2_1')
        self.assertEqual(val121, 'val1_2_1', "Get returned incorrect value.")

    def test_set_and_save(self):
        config = Config()
        config.load("testconfig.yaml")

        path = 'test1.test1_2.val1_2_1'

        # Save new value, storing orig so we can restore later
        orig_value = config.get(path)
        config.set(path, "newval")
        config.save()

        # Reopen config and get value to see if it is previously saved value
        config = Config()
        config.load("testconfig.yaml")
        saved_value = config.get(path)
        self.assertEqual(saved_value, 'newval', "New value was not saved and returned.")

        # Restore and save file
        config.set(path, orig_value)
        config.save()

    def test_get_root_nodes(self):
        config = Config()
        config.load("testconfig.yaml")

        # Get root nodes
        root_nodes = config.get_root_nodes()

        # There should be 2
        self.assertTrue(len(root_nodes) == 2, "There should be 2 root nodes.")

        # The first should be test1 and the second should be test2
        self.assertEqual(root_nodes[0], 'test1', "First root node should be 'test1'.")
        self.assertEqual(root_nodes[1], 'test2', "Second root node should be 'test2'.")


if __name__ == '__main__':
    unittest.main()
