import yaml
import wx
import logging


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


class SettingsDialog(wx.Dialog):

    # Store any settings that have changed
    changed_settings = {}

    def __init__(self, *args, **kwargs):
        # Super Constructor
        wx.Dialog.__init__(self, *args, **kwargs)
        self.SetTitle("Settings")

        # Create logger and get config
        self.__log = logging.getLogger(__name__)
        self.__settings = Config()

        # Dict of changes. Will commit only on ok
        self.__changes = {}

        # We want 2 vertical sections, the tabbed notebook and the buttons. The buttons sizer will have 2 horizontal
        # sections, one for each button.
        main_sizer = wx.BoxSizer(wx.VERTICAL)  # Notebook panel
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)  # Button sizer

        # Notebook
        self.__notebook = wx.Notebook(self, wx.ID_ANY)  # The notebook

        # A tab for each root node in config. We will store the tabs components in lists which can be accessed by the
        # index returned from notebook.GetSelectedItem()
        root_nodes = self.__settings.get_root_nodes()
        self.__tabs = []
        for node in root_nodes:
            # Create new tab
            self.__tabs.append(SettingsTab(self, self.__notebook, node))

            # Add tab to notebook
            self.__notebook.AddPage(self.__tabs[-1], node)

        # Buttons
        button_ok = wx.Button(self, label="Update")
        button_cancel = wx.Button(self, label="Cancel")
        button_sizer.Add(button_ok, 0, wx.ALL, 1)
        button_sizer.Add(button_cancel, 0, wx.ALL, 1)

        # Add notebook and button sizer to main sizer and set main sizer for window
        main_sizer.Add(self.__notebook, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(button_sizer)
        self.SetSizer(main_sizer)

        # Bind buttons &  notebook page select.
        button_ok.Bind(wx.EVT_BUTTON, self.__on_ok)
        button_cancel.Bind(wx.EVT_BUTTON, self.__on_cancel)
        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.__on_page_select)

        # Call on_page_select to select the first page
        self.__on_page_select(event=None)

    def __on_page_select(self, event):
        # Call the tabs select method to populate
        index = self.__notebook.GetSelection()
        self.__tabs[index].select()

    def __on_cancel(self, event):
        # Clear changed settings and close
        self.changed_settings = {}
        self.EndModal(wx.ID_CANCEL)
        self.Destroy()

    def __on_ok(self, event):
        # Update settings and save
        delkeys = []
        for setting in self.changed_settings:
            # Get the current and new setting
            orig_value = self.__settings.get(setting)
            new_value = self.changed_settings[setting]

            # If they are the same, discard from changes. We will use a list of items to delete (delkeys) as we cant
            # delete whilst iterating. If they are different, update settings.
            if orig_value == new_value:
                delkeys.append(setting)
            else:
                # We need to retain data type. New values will all be string as they were retrieved from textctl.
                # Get the data type of the original and cast new to it.
                new_value = type(orig_value)(new_value)
                self.__settings.set(setting, new_value)

        # Now delete the items that were the same from changed_settings. changed_settings may be used by settings
        # dialog caller.
        for key in delkeys:
            del(self.changed_settings[key])

        # Save the settings and close dialog
        self.__settings.save()
        self.EndModal(wx.ID_OK)
        self.Destroy()


class SettingsTab(wx.Panel):
    """
    A notebook tab containing the settings tree and values for a settings root node.
    """

    # Parent frame. Set during constructor
    __parent_frame = None

    # Each tab has: a tree view; a values panel; and a list of value text boxes bound to a change
    # event.
    __tree = None
    __tab_sizer = None
    __value_sizer = None
    __value_boxes = []

    def __init__(self, parent_frame, notebook, root_node):
        """
        Creates a tab for the settings notebook.

        :param parent_frame: The frame containing the notebook.
        :param notebook. The notebook that this tab should be part of.
        :param root_node. The root node for the settings
        """
        # Super Constructor
        wx.Panel.__init__(self, parent=notebook)

        # Store the parent frame and get the settings for this tab.
        self.__parent_frame = parent_frame
        settings = Config().get(root_node)

        # Create logger
        self.__log = logging.getLogger(__name__)

        # Build the tab and set it's sizer.
        self.__tab_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.__tab_sizer)

        # Create tree control
        self.__tree = wx.TreeCtrl(self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize)

        # Add root to tree and use item data to store settings path
        root = self.__tree.AddRoot(root_node)
        self.__tree.SetItemData(root, root_node)

        # Add items to root
        self.__tree = self.__build_tree(self.__tree, root, settings)

        # expand tree and add it to the sizer
        self.__tree.Expand(root)
        self.__tab_sizer.Add(self.__tree, 1, wx.ALL | wx.EXPAND, 1)

        # Add the value sizer for settings values. This is only used for spacing, as it will be overwritten when
        # tree items are selected.
        self.__value_sizer =  wx.FlexGridSizer(rows=1, cols=2, vgap=2, hgap=2)
        self.__tab_sizer.Add(self.__value_sizer, 1, wx.ALL | wx.EXPAND, 1)
        label = wx.StaticText(self, wx.ID_ANY, " ".ljust(50), style=wx.ALIGN_LEFT)
        self.__value_sizer.Add(label)

        # Bind tree selection changed
        self.__tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.__on_tree_select)

    def select(self):
        """
        To be called when this tab is selected. Populate value sizer for the selected item, If no item is selected,
        populate for root.
        :return:
        """
        selected_item = self.__tree.GetSelection()
        if selected_item.ID is None:
            root_node = self.__tree.GetRootItem()
            setting_path = self.__tree.GetItemData(root_node)
        else:
            setting_path = self.__tree.GetItemData(selected_item)

        self.__populate_settings_values(setting_path)

    def __build_tree(self, tree, node, settings):
        """
        Recursive function to build the tree from the node, using the settings
        :param tree: The tree to build
        :param node: The tree view node
        :param settings: The settings dict for the node.
        :return: The built tree
        """
        for setting in settings:
            # Get value. If dict, add the node and recursively call this function again.
            value = settings[setting]
            if type(value) is dict:
                # Add the node and set its settings path
                node_id = tree.AppendItem(node, setting)
                current_settings_path = tree.GetItemData(node)
                tree.SetItemData(node_id, f"{current_settings_path}.{setting}")

                # Recurse
                tree = self.__build_tree(tree, node_id, value)

        return tree

    def __populate_settings_values(self, setting_path):
        """
        Populates the settings in the value sizer for a settings path.

        :param setting_path:

        :return:
        """

        # Get the settings for the path
        settings = Config().get(setting_path)

        # Clear the value sizer and set its rows
        self.__value_sizer.Clear(True)
        self.__value_sizer.SetRows(len(settings))

        # Display every value that is a leaf (not dict)
        for setting in settings:
            value = settings[setting]
            if type(value) is not dict:
                # Add a label and value text box
                label = wx.StaticText(self, wx.ID_ANY, setting, style=wx.ALIGN_LEFT)
                self.__value_boxes.append(wx.TextCtrl(self, wx.ID_ANY, f"{value}", style=wx.ALIGN_LEFT))
                self.__value_sizer.AddMany([(label, 0, wx.EXPAND), (self.__value_boxes[-1], 0, wx.EXPAND)])

                # Bind to text change. We need to generate a handler as this will have a parameter.
                self.__value_boxes[-1].Bind(wx.EVT_TEXT,
                                            self.__get_on_change_evt_handler(setting_path=f'{setting_path}.{setting}'))

        self.__value_sizer.Layout()

    def __get_on_change_evt_handler(self, setting_path):
        """
        Returns a new event handler with a parameter of the settings path
        :param setting_path:
        :return:
        """
        def on_value_changed(event):
            self.__parent_frame.changed_settings[setting_path] = event.String
            self.__log.debug(f"Value changed for {setting_path}.")

        return on_value_changed

    def __on_tree_select(self, event):
        """
        Called when an item in the tree is selected. Populates the settings values
        :param event:
        :return:
        """
        # Get Selected item and check that it is a tree item
        tree_item = event.GetItem()
        if not tree_item.IsOk():
            return

        # Get the setting path from item data
        setting_path = self.__tree.GetItemData(tree_item)

        # Populate value_sizer
        self.__populate_settings_values(setting_path)
