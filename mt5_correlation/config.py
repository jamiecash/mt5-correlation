import yaml
import definitions


class Config(object):
    """
    Provides access to application configuration parameters stored in config.yaml.
    """

    config_filepath = None
    __config = None
    __instance = None

    def __new__(cls):
        """
        Singleton. Get instance of this class. Create if not already created.
        :return:
        """
        if cls.__instance is None:
            cls.__instance = super(Config, cls).__new__(cls)
        return cls.__instance

    def load(self, path):
        """
        Loads the applications config file
        :param path: Path to config file
        :return:
        """
        with open(path, 'r') as yamlfile:
            self.__config = yaml.safe_load(yamlfile)

        # Store path so that we can save later
        self.config_filepath = path

    def save(self):
        """
        Saves config file
        :return:
        """

        with open(self.config_filepath, 'w') as file:
            file.write("---\n")
            yaml.dump(self.__config, file, sort_keys=False)
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
                last = self.__config[element]
            else:
                last = last[element]

        return last

    def get_root_nodes(self):
        """
        Returns all root notes as a list
        :return: dict of root notes of YAML config file
        """
        nodes = []
        for key in self.__config:
            nodes.append(key)

        return nodes

    def set(self, path, value):
        """
        Sets a config property value
        :param path: path to property. Path separated by .
        :param value: Value to set property to
        :return:
        """
        obj = self.__config
        key_list = path.split(".")

        for k in key_list[:-1]:
            obj = obj[k]

        obj[key_list[-1]] = value
