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
    """
    A dialog box for changing settings. A tab for each root node, with a tree view on left for every branch and a text
    box for every value.
    """

    # Settings
    __settings = None  # Will set in init.

    # Store any settings that have changed
    changed_settings = {}

    def __init__(self, parent, exclude=None):
        """
        Open the settings dialog
        :param parent: The parent frame for this dialog
        :param exclude: List of settings root nodes to exclude from this dialog
        """
        # Super Constructor
        wx.Dialog.__init__(self, parent=parent, id=wx.ID_ANY, title="Settings",
                           pos=wx.Point(x=Config().get('settings_window.x'),
                                        y=Config().get('settings_window.y')),
                           size=wx.Size(width=Config().get('settings_window.width'),
                                        height=Config().get('settings_window.height')),
                           style=Config().get('settings_window.style'))

        self.SetTitle("Settings")

        # Create logger and get config
        self.__log = logging.getLogger(__name__)
        self.__settings = Config()

        # Dict of changes. Will commit only on ok
        self.__changes = {}

        # Dialog should be resizable
        self.SetWindowStyle(wx.RESIZE_BORDER)

        # Settings to exclude. Just settings_window if None. Add settings_window if not specified.
        exclude = ['settings_window'] if exclude is None else exclude
        if 'settings_window' not in exclude:
            exclude.append('settings_window')

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
            # Exclude?
            if node not in exclude:
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

        # Bind window close event
        self.Bind(wx.EVT_CLOSE, self.__on_close, self)

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
        self.Close()

    def __on_ok(self, event):
        # Update settings and save
        delkeys = []
        for setting in self.changed_settings:
            # Get the current and new setting
            orig_value = self.__settings.get(setting)
            new_value = self.changed_settings[setting]

            # We need to retain data type. New values will all be string as they were retrieved from textctl.
            # Get the data type of the original and cast new to it. Note boolean needs to be handled differently as it
            # doesn't cast directly.
            if isinstance(orig_value, bool):
                new_value = new_value.lower() in ['true', '1', 'yes', 't']
            else:
                new_value = type(orig_value)(new_value)

            # If they are the same, discard from changes. We will use a list of items to delete (delkeys) as we cant
            # delete whilst iterating. If they are different, update settings.
            if orig_value == new_value:
                delkeys.append(setting)
            else:
                self.__settings.set(setting, new_value)

        # Now delete the items that were the same from changed_settings. changed_settings may be used by settings
        # dialog caller.
        for key in delkeys:
            del(self.changed_settings[key])

        # Save the settings and close dialog
        self.__settings.save()
        self.EndModal(wx.ID_OK)
        self.Destroy()

    def __on_close(self, event):
        # Save pos and size
        x, y = self.GetPosition()
        width, height = self.GetSize()
        self.__settings.set('settings_window.x', x)
        self.__settings.set('settings_window.y', y)
        self.__settings.set('settings_window.width', width)
        self.__settings.set('settings_window.height', height)

        # Style
        style = self.GetWindowStyle()
        self.__settings.set('settings_window.style', style)


class SettingsTab(wx.Panel):
    """
    A notebook tab containing the settings tree and values for a settings root node.
    """

    # Root node for this tab
    __root_node_name = None

    # Parent frame. Set during constructor
    __parent_frame = None

    # Each tab has: a tree view; a values panel; and a list of value text boxes bound to a change
    # event.
    __tree = None
    __tab_sizer = None

    # Currently displayed value panel. Will be switched when tree menu items are selected.
    __current_value_panel = None

    def __init__(self, parent_frame, notebook, root_node):
        """
        Creates a tab for the settings notebook.

        :param parent_frame: The frame containing the notebook.
        :param notebook. The notebook that this tab should be part of.
        :param root_node. The root node name for the settings
        """
        # Super Constructor
        wx.Panel.__init__(self, parent=notebook)

        # Store the parent frame and get the settings for this tab.
        self.__parent_frame = parent_frame

        # Store the root node for this tab
        self.__root_node_name = root_node

        # Create logger
        self.__log = logging.getLogger(__name__)

        # Build the tab and set it's sizer.
        self.__tab_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.__tab_sizer)

        # Create tree control and add it to sizer
        self.__tree = SettingsTree(self, self.__root_node_name)
        self.__tab_sizer.Add(self.__tree, 1, wx.ALL | wx.EXPAND, 1)

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

        # Set the panel
        self.__switch_value_panel(setting_path)

    def __on_tree_select(self, event):
        """
        Called when an item in the tree is selected. Displays the correct settings panel
        :param event:
        :return:
        """
        # Get Selected item and check that it is a tree item
        tree_item = event.GetItem()
        if not tree_item.IsOk():
            return

        # Get the setting path from item data
        setting_path = self.__tree.GetItemData(tree_item)

        # Switch the panel
        self.__switch_value_panel(setting_path)

    def __switch_value_panel(self, setting_path):
        """
        Switched the value panel to the correct one for the settings path
        :param setting_path:
        :return:
        """
        # Get current panel and delete.
        if self.__current_value_panel is not None:
            self.__current_value_panel.Destroy()

        # Create the new value panel and add to sizer.
        self.__current_value_panel = SettingsValuePanel(self.__parent_frame, self, setting_path)
        self.__tab_sizer.Add(self.__current_value_panel, 1, wx.ALL | wx.EXPAND, 1)

        # Redraw
        self.__tab_sizer.Layout()


class SettingsTree(wx.TreeCtrl):
    """
    A Tree control containing the settings nodes settings node
    """

    __root_node_name = None

    def __init__(self, settings_tab, settings_node):
        """
        Creates a tree control for specified settings node.

        :param settings_tab. The settings_tab on which this tree control should be displayed.
        :param settings_node. The node name for the settings who's values will be presented
        """
        # Super Constructor
        wx.TreeCtrl.__init__(self, parent=settings_tab)

        # Set root node
        self.__root_node_name = settings_node

        # Build the tree
        self.__build_tree(None, self.__root_node_name)

        # Expand it
        # self.ExpandAll()

        # Set max size. Width should be best size width, height should be auto (-1)
        best_width = self.GetBestSize()[0] * 2  # Hack, best size not working
        self.SetMaxSize((best_width, -1))

    def __build_tree(self, node, node_name):
        """
        Recursive function to build the tree and value panels from the node using the settings
        :param node: The tree view node to build from. If none, builds from root.
        :param node_name. The name of the node to build from.
        """

        # Build root node if node is None
        if node is None:
            node = self.AddRoot(self.__root_node_name)
            self.SetItemData(node, self.__root_node_name)

        # Get settings
        node_path = self.GetItemData(node)
        settings = Config().get(node_path)

        # Iterate settings, adding branches. Recurse to add sub branches.
        for setting in settings:
            # Get settings path
            settings_path = f"{self.GetItemData(node)}.{setting}"

            # Get value. If dict, add the node and recursively call this function again.
            value = settings[setting]
            if type(value) is dict:
                # Add the node and set its settings path
                node_id = self.AppendItem(node, setting)
                self.SetItemData(node_id, settings_path)

                # Recurse
                self.__build_tree(node_id, value)


class SettingsValuePanel(wx.ScrolledWindow):
    """
    A panel containing text boxes for editing values for a settings node
    """

    __value_sizer = None
    __value_boxes = []

    def __init__(self, parent_frame, settings_tab, node):
        """
        Creates a panel containing values for a settings node.

        :param parent_frame: The frame containing the notebook.
        :param settings_tab. The settings_tab on which this panel should be displayed.
        :param node. The node name for the settings who's values will be presented
        """
        # Super Constructor
        wx.ScrolledWindow.__init__(self, parent=settings_tab)

        # Create logger
        self.__log = logging.getLogger(__name__)

        # Store the parent frame and get the settings for this node.
        self.__parent_frame = parent_frame
        self.__settings = Config().get(node)

        leaf_settings = {}
        for setting in self.__settings:
            if type(self.__settings[setting]) is not dict:
                leaf_settings[setting] = self.__settings[setting]

        # Add the value sizer for settings values.
        self.__value_sizer = wx.FlexGridSizer(rows=len(leaf_settings), cols=2, vgap=2, hgap=2)

        # Add the sizer to the panel
        self.SetSizer(self.__value_sizer)

        # Display every value
        for setting in leaf_settings:
            # Setting path
            setting_path = f"{node}.{setting}"

            # Value. Make sure that we display changed value if already changed
            if setting_path in self.__parent_frame.changed_settings:
                value = self.__parent_frame.changed_settings[setting_path]
            else:
                value = leaf_settings[setting]

            # Add a label and value text box
            label = wx.StaticText(self, wx.ID_ANY, setting, style=wx.ALIGN_LEFT)
            self.__value_boxes.append(wx.TextCtrl(self, wx.ID_ANY, f"{value}", style=wx.ALIGN_LEFT))
            self.__value_sizer.AddMany([(label, 0, wx.EXPAND), (self.__value_boxes[-1], 0, wx.EXPAND)])

            # Bind to text change. We need to generate a handler as this will have a parameter.
            self.__value_boxes[-1].Bind(wx.EVT_TEXT, self.__get_on_change_evt_handler(setting_path=setting_path))

        # Layout the value sizer
        self.__value_sizer.Layout()

        # Setup scrollbars
        self.SetScrollbars(1, 1, 1000, 1000)

    def __get_on_change_evt_handler(self, setting_path):
        """
        Returns a new event handler with a parameter of the settings path
        :param setting_path:
        :return:
        """

        def on_value_changed(event):
            old_val = self.__settings.get(setting_path)
            self.__parent_frame.changed_settings[setting_path] = event.String
            self.__log.debug(f"Value changed from {old_val} to {self.__parent_frame.changed_settings[setting_path]} "
                             f"for {setting_path}.")

        return on_value_changed
