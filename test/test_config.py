import unittest
from mt5_correlation.config import Config


class TestConfig(unittest.TestCase):
    def test_load_and_get(self):
        config = Config.instance()
        config.load("testconfig.yaml")
        val121 = config.get('test1.test1_2.val1_2_1')
        self.assertEqual(val121, 'val1_2_1', "Get returned incorrect value.")

    def test_set_and_save(self):
        config = Config.instance()
        config.load("testconfig.yaml")

        path = 'test1.test1_2.val1_2_1'

        # Save new value, storing orig so we can restore later
        orig_value = config.get(path)
        config.set(path, "newval")
        config.save()

        # Reopen config and get value to see if it is previously saved value
        config = Config.instance()
        config.load("testconfig.yaml")
        saved_value = config.get(path)
        self.assertEqual(saved_value, 'newval', "New value was not saved and returned.")

        # Restore and save file
        config.set(path, orig_value)
        config.save()


if __name__ == '__main__':
    unittest.main()
