import yaml
import definitions


class Config(object):
    """
    Provides access to application configuration parameters stored in config.yaml.
    """

    _config = None
    _path = None
    _instance = None

    def __init__(self):
        """
        Singleton. Raise runtime error
        """
        raise RuntimeError('Call instance() instead')

    @classmethod
    def instance(cls):
        """
        Singleton. Get instance of this class. Create if not already created.
        :return:
        """
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
        return cls._instance

    def load(self, path):
        """
        Loads the applications config file
        :param path: Path to config file
        :return:
        """
        with open(path, 'r') as yamlfile:
            self._config = yaml.safe_load(yamlfile)

        # Store path so that we can save later
        self._path = path

    def save(self):
        """
        Saves config file
        :return:
        """

        with open(self._path, 'w') as file:
            file.write("---\n")
            yaml.dump(self._config, file, sort_keys=False)
            file.write("...")

    def get(self, path):
        """
        Gets a config property value.
        :param path: path to property. Path separated by .
        :return: property value
        """

        elements = path.split('.')
        last = None

        for element in elements:
            if last is None:
                last = self._config[element]
            else:
                last = last[element]

        return last

    def set(self, path, value):
        """
        Sets a config property value
        :param path: path to property. Path separated by .
        :param value: Value to set property to
        :return:
        """
        obj = self._config
        key_list = path.split(".")

        for k in key_list[:-1]:
            obj = obj[k]

        obj[key_list[-1]] = value
