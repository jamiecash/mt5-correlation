import wx
import wx.grid
from mt5_correlation.correlation import Correlation
from mt5_correlation.config import Config, SettingsDialog
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

            # From and to dates for calculations.
            timezone = pytz.timezone("Etc/UTC")
            utc_to = datetime.now(tz=timezone)
            utc_from = utc_to - timedelta(minutes=self.config.get('monitor.from.minutes'))

            self.timer.Start(self.config.get('monitor.interval')*1000)
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
            restart_monitor_timer = False
            restart_gui_timer = False
            reload_correlations = False
            reload_logger = False

            for setting in settings_dialog.changed_settings:
                # If any 'monitor.' settings except 'monitor.divergence_threshold have changed then restart
                # monitoring timer with new settings.
                # If 'monitor.interval has changed then restart gui timer.
                # If 'monitor.monitoring_threshold' has changed, then refresh correlation data.
                # If any 'logging.' settings have changed, then reload logger config.
                if setting.startswith('monitor. ') and setting != 'monitor.divergence_threshold':
                    restart_monitor_timer = True
                if setting == 'monitor.interval':
                    restart_gui_timer = True
                if setting == 'monitor.monitoring_threshold':
                    reload_correlations = True
                if setting.startswith('logging.'):
                    reload_logger = True

            # Now perform the actions
            if restart_monitor_timer:
                self.log.debug("Settings updated. Reloading monitoring timer.")
                self.cor.stop_monitor()
                # From and to dates for calculations.
                timezone = pytz.timezone("Etc/UTC")
                utc_to = datetime.now(tz=timezone)
                utc_from = utc_to - timedelta(minutes=self.config.get('monitor.from.minutes'))
                self.cor.start_monitor(interval=self.config.get('monitor.interval'), date_from=utc_from, date_to=utc_to,
                                       min_prices=self.config.get('monitor.min_prices'),
                                       max_set_size_diff_pct=self.config.get('monitor.max_set_size_diff_pct'),
                                       overlap_pct=self.config.get('monitor.overlap_pct'),
                                       max_p_value=self.config.get('monitor.max_p_value'))
            if restart_gui_timer:
                self.log.debug("Settings updated. Restarting gui timer.")
                self.timer.Stop()
                self.timer.Start(self.config.get('monitor.interval') * 1000)

            if reload_correlations:
                self.log.debug("Settings updated. Updating monitoring threshold and reloading grid.")
                self.cor.monitoring_threshold = self.config.get("monitor.monitoring_threshold")
                self.refresh_grid(event)

            if reload_logger:
                self.log.debug("Settings updated. Reloading logger.")
                log_config = Config().get('logging')
                logging.config.dictConfig(log_config)

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
