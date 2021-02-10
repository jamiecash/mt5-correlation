import wx
import wx.grid
import wx.lib.masked as masked
from mt5_correlation.correlation import Correlation
from mt5_correlation.config import Config
from datetime import datetime, timedelta
import pytz
import pandas as pd
import logging
import definitions


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

    def __init__(self, *args, **kwds):
        self.log = logging.getLogger(__name__)
        self.config = Config.instance()

        # Create correlation instance to maintain state of calculated coefficients
        self.cor = Correlation()

        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((1235, 800))
        self.SetTitle("Monitor for Divergence")

        # Status bar
        self.statusbar = self.CreateStatusBar(1)

        # Menu Bar
        self.menubar = wx.MenuBar()
        file_menu = wx.Menu()

        # Open and save
        menu_item_open = file_menu.Append(wx.ID_ANY, "Open", "Open correlations file.")
        menu_item_save = file_menu.Append(wx.ID_ANY, "Save", "Save correlations file.")
        menu_item_saveas = file_menu.Append(wx.ID_ANY, "Save As", "Save correlations file.")

        # Calculate
        file_menu.AppendSeparator()
        menu_item_calculate = file_menu.Append(wx.ID_ANY, "Calculate", "Calculate base coefficients.")

        # Close
        file_menu.AppendSeparator()
        menu_item_exit = file_menu.Append(wx.ID_ANY, "Exit", "Close the application")

        # Add file menu and set menu bar
        self.menubar.Append(file_menu, "File")
        self.SetMenuBar(self.menubar)

        # Main window
        self.window = wx.SplitterWindow(self, wx.ID_ANY)
        self.window.SetMinimumPaneSize(20)

        self.correlations_pane = wx.Panel(self.window, wx.ID_ANY)

        sizer_grid = wx.BoxSizer(wx.VERTICAL)

        # Filter label, input box and button
        sizer_coefficient = wx.BoxSizer(wx.HORIZONTAL)
        sizer_grid.Add(sizer_coefficient, 0, 0, 0)

        label_min_coefficient = wx.StaticText(self.correlations_pane, wx.ID_ANY, "Min Coefficient (Range -1 - 1)")
        sizer_coefficient.Add(label_min_coefficient, 0, wx.ALL, 0)

        self.edit_ctrl_min_coefficient = masked.NumCtrl(self.correlations_pane, value=self.cor.min_coefficient,
                                                        allowNegative=True, min=-1, max=1, integerWidth=1,
                                                        fractionWidth=5)
        sizer_coefficient.Add(self.edit_ctrl_min_coefficient, 0, wx.ALL, 0)

        self.filter_button = wx.Button(self.correlations_pane, wx.ID_ANY, label="Filter")
        sizer_coefficient.Add(self.filter_button, 0, wx.ALL, 0)

        self.monitor_toggle = wx.ToggleButton(self.correlations_pane, wx.ID_ANY, label="Monitoring")
        sizer_coefficient.Add(self.monitor_toggle, 0, wx.ALL, 0)

        # Data table using pandas dataframe for underlying data
        self.table = DataTable(self.cor.filtered_coefficient_data)
        self.grid_correlations = wx.grid.Grid(self.correlations_pane, wx.ID_ANY, size=(1, 1))
        self.grid_correlations.SetTable(self.table, takeOwnership=True)
        self.grid_correlations.EnableEditing(0)
        self.grid_correlations.EnableDragRowSize(0)
        self.grid_correlations.EnableDragGridSize(0)
        self.grid_correlations.SetSelectionMode(wx.grid.Grid.SelectRows)
        self.grid_correlations.SetColSize(self.COLUMN_INDEX, 0)  # Index. Hide
        self.grid_correlations.SetColSize(self.COLUMN_SYMBOL1, 100)  # Symbol 1
        self.grid_correlations.SetColSize(self.COLUMN_SYMBOL2, 100)  # Symbol 2
        self.grid_correlations.SetColSize(self.COLUMN_BASE_COEFFICIENT, 100)  # Base Coefficient
        self.grid_correlations.SetColSize(self.COLUMN_DATE_FROM, 0)  # UTC Date From. Hide
        self.grid_correlations.SetColSize(self.COLUMN_DATE_TO, 0)  # UTC Date To. Hide
        self.grid_correlations.SetColSize(self.COLUMN_TIMEFRAME, 0)  # Timeframe. Hide.
        self.grid_correlations.SetColSize(self.COLUMN_LAST_CHECK, 100)  # Last Check
        self.grid_correlations.SetColSize(self.COLUMN_LAST_COEFFICIENT, 100)  # Last Coefficient
        sizer_grid.Add(self.grid_correlations, 1, wx.ALL | wx.EXPAND, 0)

        self.charts_pane = wx.Panel(self.window, wx.ID_ANY)

        # Charts
        sizer_chart = wx.BoxSizer(wx.VERTICAL)

        label_2 = wx.StaticText(self.charts_pane, wx.ID_ANY, "Charts Go Here", style=wx.ALIGN_CENTER_HORIZONTAL)
        sizer_chart.Add(label_2, 0, wx.ALIGN_CENTER_HORIZONTAL, 0)

        # Add the sizers to the panes
        self.charts_pane.SetSizer(sizer_chart)
        self.correlations_pane.SetSizer(sizer_grid)

        # Set window split to 2 panes and layout
        self.window.SplitVertically(self.correlations_pane, self.charts_pane)
        self.Layout()

        # Set up timer to refresh grid
        self.timer = wx.Timer(self)

        # Bind my buttons, timer, menu
        self.filter_button.Bind(wx.EVT_BUTTON, self.change_min_coefficient)
        self.monitor_toggle.Bind(wx.EVT_TOGGLEBUTTON, self.monitor)
        self.Bind(wx.EVT_TIMER, self.refresh_grid, self.timer)
        self.Bind(wx.EVT_MENU, self.open_file, menu_item_open)
        self.Bind(wx.EVT_MENU, self.save_file, menu_item_save)
        self.Bind(wx.EVT_MENU, self.save_file_as, menu_item_saveas)
        self.Bind(wx.EVT_MENU, self.calculate_coefficients, menu_item_calculate)
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

    def change_min_coefficient(self, event):
        self.cor.min_coefficient = self.edit_ctrl_min_coefficient.GetValue()
        self.refresh_grid(event)

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
            self.SetStatusText("Monitoring stopped.")
            self.timer.Stop()
            self.cor.stop_monitor()

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
        # Get application config
        self.config = Config.instance()

        # Get divergence threshold. This will be used by DataTable to highlight cells
        self.divergence_threshold = self.config.get('monitor.divergence_threshold')

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
        threshold = self.config.get('monitor.divergence_threshold')
        if col == MonitorFrame.COLUMN_LAST_COEFFICIENT:
            value = self.GetValue(row, col)
            if value != "":
                value = float(value)
                if value <= threshold:
                    attr.SetBackgroundColour(wx.YELLOW)
                else:
                    attr.SetBackgroundColour(wx.WHITE)

        return attr
