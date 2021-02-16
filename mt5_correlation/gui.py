import wx
import wx.grid
from mt5_correlation.correlation import Correlation
from mt5_correlation.config import Config
from datetime import datetime, timedelta
import pytz
import pandas as pd
import logging
import logging.config


class MonitorFrame(wx.Frame):

    cor = None
    rows = 0  # Need to track as we need to notify grid if row count changes.
    opened_filename = None  # So we can save to same file as we opened
    config = None  # The applications config

    COLUMN_INDEX = 0
    COLUMN_SYMBOL1 = 1
    COLUMN_SYMBOL2 = 2
    COLUMN_BASE_COEFFICIENT = 3
    COLUMN_DATE_FROM = 4
    COLUMN_DATE_TO = 5
    COLUMN_TIMEFRAME = 6
    COLUMN_LAST_CHECK = 7
    COLUMN_LAST_COEFFICIENT = 8

    def __init__(self):
        # Super
        wx.Frame.__init__(self, parent=None, id=wx.ID_ANY, title="Divergence Monitor")

        # Create logger and get config
        self.log = logging.getLogger(__name__)
        self.config = Config()

        # Create correlation instance to maintain state of calculated coefficients. Set min coefficient from config
        self.cor = Correlation()
        self.cor.monitoring_threshold = self.config.get("monitor.monitoring_threshold")

        # Status bar
        self.statusbar = self.CreateStatusBar(1)

        # Menu Bar and file menu
        self.menubar = wx.MenuBar()
        file_menu = wx.Menu()

        # File menu items
        menu_item_open = file_menu.Append(wx.ID_ANY, "Open", "Open correlations file.")
        menu_item_save = file_menu.Append(wx.ID_ANY, "Save", "Save correlations file.")
        menu_item_saveas = file_menu.Append(wx.ID_ANY, "Save As", "Save correlations file.")
        file_menu.AppendSeparator()
        menu_item_calculate = file_menu.Append(wx.ID_ANY, "Calculate", "Calculate base coefficients.")
        file_menu.AppendSeparator()
        menu_item_settings = file_menu.Append(wx.ID_ANY, "Settings", "Change application settings.")
        file_menu.AppendSeparator()
        menu_item_exit = file_menu.Append(wx.ID_ANY, "Exit", "Close the application")

        # Add file menu and set menu bar
        self.menubar.Append(file_menu, "File")
        self.SetMenuBar(self.menubar)

        # Main window. We want 2 horizontal sections, the grid showing correlations and a graph. In the correlations
        # section, we want 2 vertical sections, the monitor toggle and the correlations grid. For the toggle we want 2
        # sections, a label and a toggle.
        # ---------------------------------------------------------------
        # |label  |  toggle       |                                      |
        # |-----------------------|                                      |
        # |                       |                                      |
        # |Correlations Grid      |         Graphs                       |
        # |                       |                                      |
        # |                       |                                      |
        # |                       |                                      |
        # |                       |                                      |
        # ----------------------------------------------------------------
        panel = wx.Panel(self, wx.ID_ANY)
        toggle_sizer = wx.BoxSizer(wx.HORIZONTAL)  # Label and toggle
        correlations_sizer = wx.BoxSizer(wx.VERTICAL)  # Toggle sizer and correlations grid
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)  # Correlations sizer and graphs panel
        panel.SetSizer(main_sizer)

        # Create the label and toggle, populate the toggle sizer and add the toggle sizer to the correlations sizer
        monitor_toggle_label = wx.StaticText(panel, id=wx.ID_ANY, label="Monitoring")
        toggle_sizer.Add(monitor_toggle_label, 0, wx.ALL, 1)
        self.monitor_toggle = wx.ToggleButton(panel, wx.ID_ANY, label="Off")
        self.monitor_toggle.SetBackgroundColour(wx.RED)
        toggle_sizer.Add(self.monitor_toggle, 0, wx.ALL, 1)
        correlations_sizer.Add(toggle_sizer, 0, wx.ALL, 1)

        # Create the correlations grid. This is a data table using pandas dataframe for underlying data. Add the
        # correlations_grid to the correlations sizer.
        self.table = DataTable(self.cor.filtered_coefficient_data)
        self.grid_correlations = wx.grid.Grid(panel, wx.ID_ANY)
        self.grid_correlations.SetTable(self.table, takeOwnership=True)
        self.grid_correlations.EnableEditing(False)
        self.grid_correlations.EnableDragRowSize(False)
        self.grid_correlations.EnableDragColSize(False)
        self.grid_correlations.EnableDragGridSize(False)
        self.grid_correlations.SetSelectionMode(wx.grid.Grid.SelectRows)
        self.grid_correlations.SetRowLabelSize(0)
        self.grid_correlations.SetColSize(self.COLUMN_INDEX, 0)  # Index. Hide
        self.grid_correlations.SetColSize(self.COLUMN_SYMBOL1, 100)  # Symbol 1
        self.grid_correlations.SetColSize(self.COLUMN_SYMBOL2, 100)  # Symbol 2
        self.grid_correlations.SetColSize(self.COLUMN_BASE_COEFFICIENT, 100)  # Base Coefficient
        self.grid_correlations.SetColSize(self.COLUMN_DATE_FROM, 0)  # UTC Date From. Hide
        self.grid_correlations.SetColSize(self.COLUMN_DATE_TO, 0)  # UTC Date To. Hide
        self.grid_correlations.SetColSize(self.COLUMN_TIMEFRAME, 0)  # Timeframe. Hide.
        self.grid_correlations.SetColSize(self.COLUMN_LAST_CHECK, 100)  # Last Check
        self.grid_correlations.SetColSize(self.COLUMN_LAST_COEFFICIENT, 100)  # Last Coefficient
        self.grid_correlations.SetMinSize((520, 500))
        self.grid_correlations.SetMaxSize((520, -1))
        correlations_sizer.Add(self.grid_correlations, 1, wx.ALL | wx.EXPAND, 1)

        # Create the charts
        charts = wx.StaticText(panel, wx.ID_ANY, "Charts Go Here", style=wx.ALIGN_CENTER_HORIZONTAL)

        # Add the correlations sizer and the charts to the main sizer.
        main_sizer.Add(correlations_sizer, 1, wx.ALL | wx.EXPAND, 1)
        main_sizer.Add(charts, 1, wx.ALL | wx.EXPAND, 1)

        # Size the window.
        self.SetSize((800, 500))
        self.Layout()

        # Set up timer to refresh grid
        self.timer = wx.Timer(self)

        # Bind monitor button
        self.monitor_toggle.Bind(wx.EVT_TOGGLEBUTTON, self.monitor)

        # Bind timer
        self.Bind(wx.EVT_TIMER, self.refresh_grid, self.timer)

        # Bind menu items
        self.Bind(wx.EVT_MENU, self.open_file, menu_item_open)
        self.Bind(wx.EVT_MENU, self.save_file, menu_item_save)
        self.Bind(wx.EVT_MENU, self.save_file_as, menu_item_saveas)
        self.Bind(wx.EVT_MENU, self.calculate_coefficients, menu_item_calculate)
        self.Bind(wx.EVT_MENU, self.open_settings, menu_item_settings)
        self.Bind(wx.EVT_MENU, self.quit, menu_item_exit)

        # Bind window close event
        self.Bind(wx.EVT_CLOSE, self.on_close, self)

    def open_file(self, event):
        with wx.FileDialog(self, "Open Coefficients file", wildcard="CSV (*.csv)|*.csv",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # Load the file chosen by the user
            self.opened_filename = fileDialog.GetPath()
            self.cor.load(self.opened_filename)

            # Refresh data in grid
            self.refresh_grid(event)

            self.SetStatusText(f"File {self.opened_filename} loaded.")

    def save_file(self, event):
        self.cor.save(self.opened_filename)
        self.SetStatusText(f"File saved as {self.opened_filename}")

    def save_file_as(self, event):
        with wx.FileDialog(self, "Save Coefficients file", wildcard="CSV (*.csv)|*.csv",
                           style=wx.FD_SAVE) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # Save the file, changing opened filename so next save writes to new file
            self.opened_filename = fileDialog.GetPath()
            self.cor.save(self.opened_filename)

            self.SetStatusText(f"File saved as {self.opened_filename}")

    def calculate_coefficients(self, event):
        # set time zone to UTC to avoid local offset issues, and get from and to dates (a week ago to today)
        timezone = pytz.timezone("Etc/UTC")
        utc_to = datetime.now(tz=timezone)
        utc_from = utc_to - timedelta(days=self.config.get('calculate.from.days'))

        # Set timeframe
        timeframe = self.config.get('calculate.timeframe')

        # Calculate
        self.SetStatusText("Calculating coefficients.")
        self.cor.calculate(date_from=utc_from, date_to=utc_to,
                           timeframe=self.config.get('calculate.timeframe'),
                           min_prices=self.config.get('calculate.min_prices'),
                           max_set_size_diff_pct=self.config.get('calculate.max_set_size_diff_pct'),
                           overlap_pct=self.config.get('calculate.overlap_pct'),
                           max_p_value=self.config.get('calculate.max_p_value'))
        self.SetStatusText("")

        # Show calculated data
        self.refresh_grid(event)

    def quit(self, event):
        self.Close()

    def refresh_grid(self, event):
        """
        Refreshes grid. Notifies if rows have been added or deleted.
        :return:
        """
        self.log.debug(f"Refreshing grid. Timer running: {self.timer.IsRunning()}")

        # Update data
        self.table.data = self.cor.coefficient_data.copy()

        # Format
        self.table.data['Base Coefficient'] = self.table.data['Base Coefficient'].map('{:.5f}'.format)
        self.table.data['Last Check'] = pd.to_datetime(self.table.data['Last Check'], utc=True)
        self.table.data['Last Check'] = self.table.data['Last Check'].dt.strftime('%d-%m-%y %H:%M:%S')
        self.table.data['Last Coefficient'] = self.table.data['Last Coefficient'].map('{:.5f}'.format)

        # Remove nans. The ones from the float column wil be str nan as they have been formatted
        self.table.data = self.table.data.fillna('')
        self.table.data['Last Coefficient'] = self.table.data['Last Coefficient'].replace('nan', '')

        # Start refresh
        self.grid_correlations.BeginBatch()

        # Check if num rows in dataframe has changed, and send appropriate APPEND or DELETE messages
        cur_rows = len(self.cor.filtered_coefficient_data.index)
        if cur_rows < self.rows:
            # Data has been deleted. Send message
            msg = wx.grid.GridTableMessage(self.table, wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED,
                                           self.rows - cur_rows, self.rows - cur_rows)
            self.grid_correlations.ProcessTableMessage(msg)
        elif cur_rows > self.rows:
            # Data has been added. Send message
            msg = wx.grid.GridTableMessage(self.table, wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED,
                                           cur_rows - self.rows)  # how many
            self.grid_correlations.ProcessTableMessage(msg)

        self.grid_correlations.EndBatch()

        # Send updated message
        msg = wx.grid.GridTableMessage(self.table, wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES)
        self.grid_correlations.ProcessTableMessage(msg)

        # Update row count
        self.rows = cur_rows

    def monitor(self, event):
        # Check state of toggle button. If on, then start monitoring, else stop
        if self.monitor_toggle.GetValue():
            self.log.debug("Starting monitoring.")
            self.monitor_toggle.SetBackgroundColour(wx.GREEN)
            self.monitor_toggle.SetLabelText("On")
            self.SetStatusText("Monitoring for changes to coefficients.")

            # Calculate correlations fro last 10 mins
            timezone = pytz.timezone("Etc/UTC")
            utc_to = datetime.now(tz=timezone)
            utc_from = utc_to - timedelta(minutes=self.config.get('monitor.from.minutes'))

            self.timer.Start(10000)
            self.cor.start_monitor(interval=self.config.get('monitor.interval'), date_from=utc_from, date_to=utc_to,
                                   min_prices=self.config.get('monitor.min_prices'),
                                   max_set_size_diff_pct=self.config.get('monitor.max_set_size_diff_pct'),
                                   overlap_pct=self.config.get('monitor.overlap_pct'),
                                   max_p_value=self.config.get('monitor.max_p_value'))
        else:
            self.log.debug("Stopping monitoring.")
            self.monitor_toggle.SetBackgroundColour(wx.RED)
            self.monitor_toggle.SetLabelText("Off")
            self.SetStatusText("Monitoring stopped.")
            self.timer.Stop()
            self.cor.stop_monitor()

    def open_settings(self, event):
        """
        Opens the settings dialog
        :return:
        """
        settings_dialog = SettingsDialog(self)
        res = settings_dialog.ShowModal()
        if res == wx.ID_OK:
            # Reload relevant parts of app
            # TODO: Reload relevant parts of app once settings have changed. Stop and restart monitoring,
            #       reload logger, filter data, refresh data window.
            self.log.debug("Settings updated. Reloading logger.")
            log_config = Config().get('logging')
            logging.config.dictConfig(log_config)
        settings_dialog.Destroy()

    def on_close(self, event):
        """
        Window closing. Save coefficients and stop monitoring.
        :param event:
        :return:
        """
        if self.opened_filename is not None:
            self.cor.save(self.opened_filename)

        self.cor.stop_monitor()

        event.Skip()


class DataTable(wx.grid.GridTableBase):
    """
    A data table that holds data in a pandas dataframe
    """
    def __init__(self, data=None):
        wx.grid.GridTableBase.__init__(self)
        self.headerRows = 1
        if data is None:
            data = pd.DataFrame()
        self.data = data

        # Get divergence threshold from app config
        self.divergence_threshold = Config().get('monitor.divergence_threshold')

    def GetNumberRows(self):
        return len(self.data)

    def GetNumberCols(self):
        return len(self.data.columns) + 1

    def GetValue(self, row, col):
        if col == 0:
            return self.data.index[row]
        return self.data.iloc[row, col - 1]

    def SetValue(self, row, col, value):
        self.data.iloc[row, col - 1] = value

    def GetColLabelValue(self, col):
        if col == 0:
            if self.data.index.name is None:
                return 'Index'
            else:
                return self.data.index.name
        return str(self.data.columns[col - 1])

    def GetTypeName(self, row, col):
        return wx.grid.GRID_VALUE_STRING

    def GetAttr(self, row, col, prop):
        attr = wx.grid.GridCellAttr()

        # If column is last coefficient, get value and check against threshold. Highlight if diverged.
        threshold = Config().get('monitor.divergence_threshold')
        if col == MonitorFrame.COLUMN_LAST_COEFFICIENT:
            value = self.GetValue(row, col)
            if value != "":
                value = float(value)
                if value <= threshold:
                    attr.SetBackgroundColour(wx.YELLOW)
                else:
                    attr.SetBackgroundColour(wx.WHITE)

        return attr


class SettingsDialog(wx.Dialog):

    # Store any settings that have changed
    changed_settings = {}

    def __init__(self, *args, **kwargs):
        # Super Constructor
        wx.Dialog.__init__(self, *args, **kwargs)
        self.SetTitle("Settings")

        # Create logger and get config
        self.log = logging.getLogger(__name__)

        # Get settings
        self.__settings = Config()

        # Dict of changes. Will commit only on ok
        self.__changes = {}

        # We want 2 vertical sections, the tabbed notebook and the buttons. The buttons sizer will have 2 horizontal
        # sections, one for each button.
        # -------------------------
        # |Tabbed notebook        |
        # |                       |
        # |                       |
        # |                       |
        # |                       |
        # |-----------------------|
        # |ok | cancel            |
        # -------------------------
        main_sizer = wx.BoxSizer(wx.VERTICAL)  # Notebook panel
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)  # Button sizer

        # Notebook
        self.__notebook = wx.Notebook(self, wx.ID_ANY)  # The notebook

        # A tab for each root node in config. We will store the tabs components in lists which can be accessed by the
        # index returned from notebook.GetSelectedItem()
        root_nodes = self.__settings.get_root_nodes()
        self.__tabs = []
        self.__trees = []
        self.__tab_sizers = []
        self.__value_sizers = []
        self.__value_boxes = []  # We need to store these as they will all be bound to a change event
        # self.roots = []
        for node in root_nodes:
            # Create new tab
            self.__tabs.append(wx.Panel(self.__notebook, wx.ID_ANY))
            self.__tab_sizers.append(wx.BoxSizer(wx.HORIZONTAL))
            self.__tabs[-1].SetSizer(self.__tab_sizers[-1])

            # Get settings items for tab / node
            node_settings = self.__settings.get(node)

            # Create tree control
            self.__trees.append(wx.TreeCtrl(self.__tabs[-1], wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize))

            # Add root to tree and use item data to store settings path
            root = self.__trees[-1].AddRoot(node)
            self.__trees[-1].SetItemData(root, node)

            # Add items to root
            self.__trees[-1] = self.__build_tree(self.__trees[-1], root, node_settings)

            # expand tree and add it to the sizer
            self.__trees[-1].Expand(root)
            self.__tab_sizers[-1].Add(self.__trees[-1], 1, wx.ALL | wx.EXPAND, 1)

            # Add the value sizer for settings values. This is only used for spacing, as it will be overwritten when
            # tree items are selected.
            self.__value_sizers.append(wx.FlexGridSizer(rows=1, cols=2, vgap=2, hgap=2))
            self.__tab_sizers[-1].Add(self.__value_sizers[-1], 1, wx.ALL | wx.EXPAND, 1)
            label = wx.StaticText(self.__tabs[-1], wx.ID_ANY, " ".ljust(50), style=wx.ALIGN_LEFT)
            self.__value_sizers[-1].Add(label)

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

        # Bind buttons, notebook page select and tree control select item
        button_ok.Bind(wx.EVT_BUTTON, self.__on_ok)
        button_cancel.Bind(wx.EVT_BUTTON, self.__on_cancel)
        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.__on_page_select)
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.__on_tree_select)

        # Call on_page_select to select the first page
        self.__on_page_select(event=None)

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

    def __populate_settings_values(self, setting_path, index):
        """
        Populates the settings in the value sizer for a settings path.

        :param setting_path:
        :param index: The tab index containing the value_sizer to populate

        :return:
        """
        # Get the setting values
        settings = self.__settings.get(setting_path)

        # Get the value sizer, clear it and set its rows
        value_sizer = self.__value_sizers[index]
        value_sizer.Clear(True)
        value_sizer.SetRows(len(settings))

        # Display every value that is a leaf (not dict)
        for setting in settings:
            value = settings[setting]
            if type(value) is not dict:
                # Add a label and value text box
                label = wx.StaticText(self.__tabs[index], wx.ID_ANY, setting, style=wx.ALIGN_LEFT)
                self.__value_boxes.append(wx.TextCtrl(self.__tabs[index], wx.ID_ANY, f"{value}", style=wx.ALIGN_LEFT))
                value_sizer.AddMany([(label, 0, wx.EXPAND), (self.__value_boxes[-1], 0, wx.EXPAND)])

                # Bind to text change. We need to generate a handler as this will have a parameter.
                self.__value_boxes[-1].Bind(wx.EVT_TEXT,
                                            self.__get_on_change_evt_handler(setting_path=f'{setting_path}.{setting}'))

        value_sizer.Layout()

    def __on_page_select(self, event):
        # Populate value sizer for the selected item, If no item is selected, populate for root.
        index = self.__notebook.GetSelection()
        selected_item = self.__trees[index].GetSelection()
        if selected_item.ID is None:
            root_node = self.__trees[index].GetRootItem()
            setting_path = self.__trees[index].GetItemData(root_node)
        else:
            setting_path = self.__trees[index].GetItemData(selected_item)

        self.__populate_settings_values(setting_path, index)

    def __on_tree_select(self, event):
        # Get Selected item and check that it is a tree item
        tree_item = event.GetItem()
        if not tree_item.IsOk():
            return

        # Get the index of the current tab
        index = self.__notebook.GetSelection()

        # Get the setting path from item data
        setting_path = self.__trees[index].GetItemData(tree_item)

        # Populate value_sizer
        self.__populate_settings_values(setting_path, index)

    def __on_cancel(self, e):
        # Clear changed settings and close
        self.changed_settings = {}
        self.EndModal(wx.ID_CANCEL)
        self.Destroy()

    def __on_ok(self, e):
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

    def __get_on_change_evt_handler(self, setting_path):
        def on_value_changed(event):
            self.changed_settings[setting_path] = event.String
            self.log.debug(f"Value changed for {setting_path}.")

        return on_value_changed
