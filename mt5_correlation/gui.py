import wx
import wx.grid
import matplotlib.pyplot as plt
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
import matplotlib.dates
import matplotlib

from mt5_correlation.correlation import Correlation
from mt5_correlation.config import Config, SettingsDialog
from datetime import datetime, timedelta
import pytz
import pandas as pd
import logging
import logging.config

matplotlib.use('WXAgg')


class MonitorFrame(wx.Frame):

    __cor = None
    __rows = 0  # Need to track as we need to notify grid if row count changes.
    __opened_filename = None  # So we can save to same file as we opened
    __config = None  # The applications config

    __selected_correlation = []  # List of Symbol 1 & Symbol 2

    # Columns for coefficient table
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
        wx.Frame.__init__(self, parent=None, id=wx.ID_ANY, title="Divergence Monitor",
                          pos=wx.Point(x=Config().get('window.x'),
                                       y=Config().get('window.y')),
                          size=wx.Size(width=Config().get('window.width'),
                                       height=Config().get('window.height')),
                          style=Config().get('window.style'))

        # Create logger and get config
        self.__log = logging.getLogger(__name__)
        self.__config = Config()

        # Create correlation instance to maintain state of calculated coefficients. Set min coefficient from config
        self.__cor = Correlation()
        self.__cor.monitoring_threshold = self.__config.get("monitor.monitoring_threshold")

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
        self.__main_sizer = wx.BoxSizer(wx.HORIZONTAL)  # Correlations sizer and graphs panel
        panel.SetSizer(self.__main_sizer)

        # Create the label and toggle, populate the toggle sizer and add the toggle sizer to the correlations sizer
        monitor_toggle_label = wx.StaticText(panel, id=wx.ID_ANY, label="Monitoring")
        toggle_sizer.Add(monitor_toggle_label, 0, wx.ALL, 1)
        self.monitor_toggle = wx.ToggleButton(panel, wx.ID_ANY, label="Off")
        self.monitor_toggle.SetBackgroundColour(wx.RED)
        toggle_sizer.Add(self.monitor_toggle, 0, wx.ALL, 1)
        correlations_sizer.Add(toggle_sizer, 0, wx.ALL, 1)

        # Create the correlations grid. This is a data table using pandas dataframe for underlying data. Add the
        # correlations_grid to the correlations sizer.
        self.table = DataTable(self.__cor.filtered_coefficient_data)
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

        # Create the charts and hide as we have no data to display yet
        self.__graph = GraphPanel(panel)
        self.__graph.Hide()

        # Add the correlations sizer and the charts to the main sizer.
        self.__main_sizer.Add(correlations_sizer, 0, wx.ALL | wx.EXPAND, 1)
        self.__main_sizer.Add(self.__graph, 1, wx.ALL | wx.EXPAND, 1)

        # Layout the window.
        self.Layout()

        # Set up timer to refresh grid
        self.timer = wx.Timer(self)

        # Bind monitor button
        self.monitor_toggle.Bind(wx.EVT_TOGGLEBUTTON, self.monitor)

        # Bind timer
        self.Bind(wx.EVT_TIMER, self.__timer_event, self.timer)

        # Bind menu items
        self.Bind(wx.EVT_MENU, self.open_file, menu_item_open)
        self.Bind(wx.EVT_MENU, self.save_file, menu_item_save)
        self.Bind(wx.EVT_MENU, self.save_file_as, menu_item_saveas)
        self.Bind(wx.EVT_MENU, self.calculate_coefficients, menu_item_calculate)
        self.Bind(wx.EVT_MENU, self.open_settings, menu_item_settings)
        self.Bind(wx.EVT_MENU, self.quit, menu_item_exit)

        # Bind row select
        self.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.select_cell, self.grid_correlations)

        # Bind window close event
        self.Bind(wx.EVT_CLOSE, self.on_close, self)

    def open_file(self, event):
        with wx.FileDialog(self, "Open Coefficients file", wildcard="cpd (*.cpd)|*.cpd",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # Load the file chosen by the user.
            self.__opened_filename = fileDialog.GetPath()

            self.SetStatusText(f"Loading file {self.__opened_filename}.")
            self.__cor.load(self.__opened_filename)

            # Refresh data in grid
            self.refresh_grid()

            self.SetStatusText(f"File {self.__opened_filename} loaded.")

    def save_file(self, event):
        self.SetStatusText(f"Saving file as {self.__opened_filename}")

        if self.__opened_filename is None:
            self.save_file_as(event)
        else:
            self.__cor.save(self.__opened_filename)

        self.SetStatusText(f"File saved as {self.__opened_filename}")

    def save_file_as(self, event):
        with wx.FileDialog(self, "Save Coefficients file", wildcard="cpd (*.cpd)|*.cpd",
                           style=wx.FD_SAVE) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # Save the file and price data file, changing opened filename so next save writes to new file
            self.SetStatusText(f"Saving file as {self.__opened_filename}")

            self.__opened_filename = fileDialog.GetPath()
            self.__cor.save(self.__opened_filename)

            self.SetStatusText(f"File saved as {self.__opened_filename}")

    def calculate_coefficients(self, event):
        # set time zone to UTC to avoid local offset issues, and get from and to dates (a week ago to today)
        timezone = pytz.timezone("Etc/UTC")
        utc_to = datetime.now(tz=timezone)
        utc_from = utc_to - timedelta(days=self.__config.get('calculate.from.days'))

        # Calculate
        self.SetStatusText("Calculating coefficients.")
        self.__cor.calculate(date_from=utc_from, date_to=utc_to,
                           timeframe=self.__config.get('calculate.timeframe'),
                           min_prices=self.__config.get('calculate.min_prices'),
                           max_set_size_diff_pct=self.__config.get('calculate.max_set_size_diff_pct'),
                           overlap_pct=self.__config.get('calculate.overlap_pct'),
                           max_p_value=self.__config.get('calculate.max_p_value'))
        self.SetStatusText("")

        # Show calculated data
        self.refresh_grid()

    def quit(self, event):
        # Close
        self.Close()

    def refresh_grid(self):
        """
        Refreshes grid. Notifies if rows have been added or deleted.
        :return:
        """
        self.__log.debug(f"Refreshing grid. Timer running: {self.timer.IsRunning()}")

        # Update data
        self.table.data = self.__cor.coefficient_data.copy()

        # Format
        self.table.data.loc[:, 'Base Coefficient'] = self.table.data['Base Coefficient'].map('{:.5f}'.format)
        self.table.data.loc[:, 'Last Check'] = pd.to_datetime(self.table.data['Last Check'], utc=True)
        self.table.data.loc[:, 'Last Check'] = self.table.data['Last Check'].dt.strftime('%d-%m-%y %H:%M:%S')
        self.table.data.loc[:, 'Last Coefficient'] = self.table.data['Last Coefficient'].map('{:.5f}'.format)

        # Remove nans. The ones from the float column will be str nan as they have been formatted
        self.table.data = self.table.data.fillna('')
        self.table.data.loc[:, 'Last Coefficient'] = self.table.data['Last Coefficient'].replace('nan', '')

        # Start refresh
        self.grid_correlations.BeginBatch()

        # Check if num rows in dataframe has changed, and send appropriate APPEND or DELETE messages
        cur_rows = len(self.__cor.filtered_coefficient_data.index)
        if cur_rows < self.__rows:
            # Data has been deleted. Send message
            msg = wx.grid.GridTableMessage(self.table, wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED,
                                           self.__rows - cur_rows, self.__rows - cur_rows)
            self.grid_correlations.ProcessTableMessage(msg)
        elif cur_rows > self.__rows:
            # Data has been added. Send message
            msg = wx.grid.GridTableMessage(self.table, wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED,
                                           cur_rows - self.__rows)  # how many
            self.grid_correlations.ProcessTableMessage(msg)

        self.grid_correlations.EndBatch()

        # Send updated message
        msg = wx.grid.GridTableMessage(self.table, wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES)
        self.grid_correlations.ProcessTableMessage(msg)

        # Update row count
        self.__rows = cur_rows

    def monitor(self, event):
        # Check state of toggle button. If on, then start monitoring, else stop
        if self.monitor_toggle.GetValue():
            self.__log.info("Starting monitoring.")
            self.monitor_toggle.SetBackgroundColour(wx.GREEN)
            self.monitor_toggle.SetLabelText("On")
            self.SetStatusText("Monitoring for changes to coefficients.")

            self.timer.Start(self.__config.get('monitor.interval')*1000)

            # Autosave filename
            filename = self.__opened_filename if self.__opened_filename is not None else 'autosave.cpd'

            self.__cor.start_monitor(interval=self.__config.get('monitor.interval'),
                                     from_mins=self.__config.get('monitor.from.minutes'),
                                     min_prices=self.__config.get('monitor.min_prices'),
                                     max_set_size_diff_pct=self.__config.get('monitor.max_set_size_diff_pct'),
                                     overlap_pct=self.__config.get('monitor.overlap_pct'),
                                     max_p_value=self.__config.get('monitor.max_p_value'),
                                     cache_time=self.__config.get('monitor.tick_cache_time'),
                                     autosave=self.__config.get('monitor.autosave'),
                                     filename=filename)
        else:
            self.__log.info("Stopping monitoring.")
            self.monitor_toggle.SetBackgroundColour(wx.RED)
            self.monitor_toggle.SetLabelText("Off")
            self.SetStatusText("Monitoring stopped.")
            self.timer.Stop()
            self.__cor.stop_monitor()

    def open_settings(self, event):
        """
        Opens the settings dialog
        :return:
        """
        settings_dialog = SettingsDialog(self, size=(500, 250))
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
                if setting.startswith('monitor.') and setting != 'monitor.divergence_threshold':
                    restart_monitor_timer = True
                if setting == 'monitor.interval':
                    restart_gui_timer = True
                if setting == 'monitor.monitoring_threshold':
                    reload_correlations = True
                if setting.startswith('logging.'):
                    reload_logger = True

            # Now perform the actions
            if restart_monitor_timer:
                self.__log.info("Settings updated. Reloading monitoring timer.")
                self.__cor.stop_monitor()
                # From and to dates for calculations.
                timezone = pytz.timezone("Etc/UTC")
                utc_to = datetime.now(tz=timezone)
                utc_from = utc_to - timedelta(minutes=self.__config.get('monitor.from.minutes'))
                self.__cor.start_monitor(interval=self.__config.get('monitor.interval'),
                                         from_mins=self.__config.get('monitor.from.minutes'),
                                         min_prices=self.__config.get('monitor.min_prices'),
                                         max_set_size_diff_pct=self.__config.get('monitor.max_set_size_diff_pct'),
                                         overlap_pct=self.__config.get('monitor.overlap_pct'),
                                         max_p_value=self.__config.get('monitor.max_p_value'))
            if restart_gui_timer:
                self.__log.info("Settings updated. Restarting gui timer.")
                self.timer.Stop()
                self.timer.Start(self.__config.get('monitor.interval') * 1000)

            if reload_correlations:
                self.__log.info("Settings updated. Updating monitoring threshold and reloading grid.")
                self.__cor.monitoring_threshold = self.__config.get("monitor.monitoring_threshold")
                self.refresh_grid()

            if reload_logger:
                self.__log.info("Settings updated. Reloading logger.")
                log_config = Config().get('logging')
                logging.config.dictConfig(log_config)

    def on_close(self, event):
        """
        Window closing. Save coefficients and stop monitoring.
        :param event:
        :return:
        """
        # Save pos and size
        x, y = self.GetPosition()
        width, height = self.GetSize()
        self.__config.set('window.x', x)
        self.__config.set('window.y', y)
        self.__config.set('window.width', width)
        self.__config.set('window.height', height)

        # Style
        style = self.GetWindowStyle()
        self.__config.set('window.style', style)

        self.__config.save()

        # Stop monitoring
        self.__cor.stop_monitor()

        # Kill graph as it seems to be stopping script from ending
        self.__graph = None

        # End
        event.Skip()

    def select_cell(self, event):
        """
        A cell was selected. Show the graph for the correlation.
        :param event:
        :return:
        """
        # Get row and symbols.
        row = event.GetRow()
        symbol1 = self.grid_correlations.GetCellValue(row, self.COLUMN_SYMBOL1)
        symbol2 = self.grid_correlations.GetCellValue(row, self.COLUMN_SYMBOL2)
        self.__selected_correlation = [symbol1, symbol2]

        self.show_graph(symbol1, symbol2)

    def show_graph(self, symbol1, symbol2):
        """
        Displays the graph for the specified symbols correlation history
        :param symbol1:
        :param symbol2:
        :return:
        """
        # Get the price data for the base coefficient calculation, tick data to calculate last coefficient and  and the
        # coefficient history data
        symbol_1_price_data = self.__cor.get_price_data(symbol1)
        symbol_2_price_data = self.__cor.get_price_data(symbol2)
        symbol_1_ticks = self.__cor.get_ticks(symbol1, cache_only=True)
        symbol_2_ticks = self.__cor.get_ticks(symbol2, cache_only=True)
        history_data = self.__cor.get_coefficient_history(symbol1, symbol2)
        times = history_data['UTC Date To']
        coefficients = history_data['Coefficient']

        # Display if we have any data
        self.__log.debug(f"Refreshing history graph {symbol1}:{symbol2}.")
        self.__graph.draw(times=times, coefficients=coefficients, prices=[symbol_1_price_data, symbol_2_price_data],
                          ticks=[symbol_1_ticks, symbol_2_ticks], symbols=[symbol1, symbol2])

        # Un-hide and layout if hidden
        if not self.__graph.IsShown():
            self.__graph.Show()
            self.__main_sizer.Layout()

    def __timer_event(self, event):
        """
        Called on timer event. Refreshes grid and updatates selected graph.
        :return:
        """
        self.refresh_grid()
        if len(self.__selected_correlation) == 2:
            self.show_graph(symbol1=self.__selected_correlation[0], symbol2=self.__selected_correlation[1])


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


class GraphPanel(wx.Panel):
    def __init__(self, parent):
        """
        A panel to show the graphs
        :param parent: The parent panel
        """
        # Super
        wx.Panel.__init__(self, parent)

        # 3  axis, 2 price data for calculate, 2 price data for last coefficient and coefficient history.
        # All will have axis labels and top and right boarders
        # removed
        self.__fig, self.__axes = plt.subplots(nrows=5, ncols=1)

        # Create the canvas
        self.__canvas = FigureCanvas(self, -1, self.__fig)

        # Date format for x axes
        self.__tick_fmt_date = matplotlib.dates.DateFormatter('%d-%b')
        self.__tick_fmt_time = matplotlib.dates.DateFormatter('%H:%M:%S')

        # Sizer etc.
        self.__sizer = wx.BoxSizer(wx.VERTICAL)
        self.__sizer.Add(self.__canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        self.SetSizer(self.__sizer)
        self.Fit()

    def __del__(self):
        # Close all plots
        plt.close('all')
        self.__axes = None
        self.__fig = None

    def draw(self, times, coefficients, prices=None, symbols=None, ticks=None):
        """
        Plot the correlations.
        :param times: Series of time values for x axis for coefficient history chart
        :param coefficients: Series of coefficients values for y axis of coefficient history chart
        :param prices: Price data used to calculate base coefficient. List [Symbol1 Price Data, Symbol 2 Price Data]
        :param symbols: Symbols. List [Symbol1, Symbol2]
        :param ticks: Ticks used to calculate last coefficient. List [Symbol1, Symbol2]
        :return:
        """
        # Clear. We will need to redraw
        for ax in self.__axes:
            ax.clear()

        if symbols is not None and len(symbols) == 2:
            # Axis ranges
            price_chart_date_range = [min(min(prices[0]['time']), min(prices[1]['time'])),
                                      max(max(prices[0]['time']), max(prices[1]['time']))]
            tick_chart_date_range = [min(min(ticks[0]['time']), min(ticks[1]['time'])),
                                     max(max(ticks[0]['time']), max(ticks[1]['time']))]

            # Chart config
            titles = [f"Base Coefficient Price Data for {symbols[0]}", f"Base Coefficient Price Data for {symbols[1]}",
                      f"Coefficient Tick Data for {symbols[0]}", f"Coefficient Tick Data for {symbols[1]}",
                      f"Coefficient History for {symbols[0]}:{symbols[1]}"]
            xlims = [price_chart_date_range, price_chart_date_range, tick_chart_date_range, tick_chart_date_range, None]
            ylims = [None, None, None, None, [-1, 1]]
            xlabels = [None, None, None, None, None]
            ylabels = ['Price', 'Price', 'Price', 'Price', 'Coefficient']
            tick_labels = [[], prices[1]['time'], [], ticks[1]['time'], times]
            mtick_fmts = [None, self.__tick_fmt_date, None, self.__tick_fmt_time, self.__tick_fmt_time]
            mtick_rot = [0, 45, 0, 45, 45]
            xdata = [prices[0]['time'], prices[1]['time'], ticks[0]['time'], ticks[1]['time'], times]
            ydata = [prices[0]['close'], prices[1]['close'], ticks[0]['ask'], ticks[1]['ask'], coefficients]
            types = ['plot', 'plot', 'plot', 'plot', 'scatter']

            # Draw 5 charts
            for index in range(0, len(self.__axes)):
                # Titles and axis labels
                self.__axes[index].set_title(titles[index])
                self.__axes[index].set_xlabel(xlabels[index])
                self.__axes[index].set_ylabel(ylabels[index])

                # Limits
                if xlims[index] is not None:
                    self.__axes[index].set_xlim(xlims[index])

                if ylims[index] is not None:
                    self.__axes[index].set_ylim(ylims[index])

                # Tick labels and formats
                self.__axes[index].xaxis.set_ticklabels(tick_labels[index])
                if mtick_fmts[index] is not None:
                    self.__axes[index].xaxis.set_major_formatter(mtick_fmts[index])
                plt.setp(self.__axes[index].xaxis.get_majorticklabels(), rotation=mtick_rot[index])

                # Remove typ and right boarders
                self.__axes[index].spines["top"].set_visible(False)
                self.__axes[index].spines["right"].set_visible(False)

                # Plot
                if types[index] == 'plot':
                    self.__axes[index].plot(xdata[index], ydata[index])
                elif types[index] == 'scatter':
                    self.__axes[index].scatter(xdata[index], ydata[index], s=1)

            # Layout with padding between charts
            self.__fig.tight_layout(pad=0.5)

        # Redraw canvas
        self.__canvas.draw()
