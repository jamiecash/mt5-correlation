import wx
import wx.grid
import matplotlib.pyplot as plt
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
import matplotlib.dates
import matplotlib
import matplotlib.ticker as mticker

from mt5_correlation import correlation as cor
import wxconfig as cfg
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
    COLUMN_LAST_CALCULATION = 7
    COLUMN_STATUS = 8

    def __init__(self):
        # Super
        wx.Frame.__init__(self, parent=None, id=wx.ID_ANY, title="Divergence Monitor",
                          pos=wx.Point(x=cfg.Config().get('window.x'),
                                       y=cfg.Config().get('window.y')),
                          size=wx.Size(width=cfg.Config().get('window.width'),
                                       height=cfg.Config().get('window.height')),
                          style=cfg.Config().get('window.style'))

        # Create logger and get config
        self.__log = logging.getLogger(__name__)
        self.__config = cfg.Config()

        # Create correlation instance to maintain state of calculated coefficients. Set min coefficient from config
        self.__cor = cor.Correlation(monitoring_threshold=self.__config.get("monitor.monitoring_threshold"),
                                     divergence_threshold=self.__config.get("monitor.divergence_threshold"),
                                     monitor_inverse=self.__config.get("monitor.monitor_inverse"))

        # Status bar. 2 fields, one for monitoring status and one for general status. On open, monitoring status is not
        # monitoring. SetBackgroundColour will change colour of both. Couldn't find a way to set on single field only.
        self.__statusbar = self.CreateStatusBar(2)
        self.__statusbar.SetStatusWidths([100, -1])
        self.SetStatusText("Not Monitoring", 0)

        # Menu Bar
        self.menubar = wx.MenuBar()

        # File menu and items
        file_menu = wx.Menu()
        menu_item_open = file_menu.Append(wx.ID_ANY, "Open", "Open correlations file.")
        menu_item_save = file_menu.Append(wx.ID_ANY, "Save", "Save correlations file.")
        menu_item_saveas = file_menu.Append(wx.ID_ANY, "Save As", "Save correlations file.")
        file_menu.AppendSeparator()
        menu_item_settings = file_menu.Append(wx.ID_ANY, "Settings", "Change application settings.")
        file_menu.AppendSeparator()
        menu_item_exit = file_menu.Append(wx.ID_ANY, "Exit", "Close the application")
        self.menubar.Append(file_menu, "File")

        # Coefficient menu and items
        coef_menu = wx.Menu()
        menu_item_calculate = coef_menu.Append(wx.ID_ANY, "Calculate", "Calculate base coefficients.")
        self.__menu_item_monitor = coef_menu.Append(wx.ID_ANY, "Monitor", "Monitor correlated pairs for changes to "
                                                                          "coefficient.", kind=wx.ITEM_CHECK)
        coef_menu.AppendSeparator()
        menu_item_clear = coef_menu.Append(wx.ID_ANY, "Clear", "Clear coefficient and price history.")
        self.menubar.Append(coef_menu, "Coefficient")

        # Set menu bar
        self.SetMenuBar(self.menubar)

        # Main window. We want 2 horizontal sections, the grid showing correlations and a graph.
        panel = wx.Panel(self, wx.ID_ANY)
        correlations_sizer = wx.BoxSizer(wx.VERTICAL)  # Correlations grid
        self.__main_sizer = wx.BoxSizer(wx.HORIZONTAL)  # Correlations sizer and graphs panel
        panel.SetSizer(self.__main_sizer)

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
        self.grid_correlations.SetColSize(self.COLUMN_LAST_CALCULATION, 0)  # Last Calculation. Hide
        self.grid_correlations.SetColSize(self.COLUMN_STATUS, 100)  # Status
        self.grid_correlations.SetMinSize((420, 500))
        self.grid_correlations.SetMaxSize((420, -1))
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

        # Bind timer
        self.Bind(wx.EVT_TIMER, self.__timer_event, self.timer)

        # Bind menu items
        self.Bind(wx.EVT_MENU, self.open_file, menu_item_open)
        self.Bind(wx.EVT_MENU, self.save_file, menu_item_save)
        self.Bind(wx.EVT_MENU, self.save_file_as, menu_item_saveas)
        self.Bind(wx.EVT_MENU, self.calculate_coefficients, menu_item_calculate)
        self.Bind(wx.EVT_MENU, self.open_settings, menu_item_settings)
        self.Bind(wx.EVT_MENU, self.__monitor, self.__menu_item_monitor)
        self.Bind(wx.EVT_MENU, self.__clear_history, menu_item_clear)
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

            self.SetStatusText(f"Loading file {self.__opened_filename}.", 1)
            self.__cor.load(self.__opened_filename)

            # Refresh data in grid
            self.__refresh_grid()

            self.SetStatusText(f"File {self.__opened_filename} loaded.", 1)

    def save_file(self, event):
        self.SetStatusText(f"Saving file as {self.__opened_filename}", 1)

        if self.__opened_filename is None:
            self.save_file_as(event)
        else:
            self.__cor.save(self.__opened_filename)

        self.SetStatusText(f"File saved as {self.__opened_filename}", 1)

    def save_file_as(self, event):
        with wx.FileDialog(self, "Save Coefficients file", wildcard="cpd (*.cpd)|*.cpd",
                           style=wx.FD_SAVE) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # Save the file and price data file, changing opened filename so next save writes to new file
            self.SetStatusText(f"Saving file as {self.__opened_filename}", 1)

            self.__opened_filename = fileDialog.GetPath()
            self.__cor.save(self.__opened_filename)

            self.SetStatusText(f"File saved as {self.__opened_filename}", 1)

    def calculate_coefficients(self, event):
        # set time zone to UTC to avoid local offset issues, and get from and to dates (a week ago to today)
        timezone = pytz.timezone("Etc/UTC")
        utc_to = datetime.now(tz=timezone)
        utc_from = utc_to - timedelta(days=self.__config.get('calculate.from.days'))

        # Calculate
        self.SetStatusText("Calculating coefficients.", 1)
        self.__cor.calculate(date_from=utc_from, date_to=utc_to,
                             timeframe=self.__config.get('calculate.timeframe'),
                             min_prices=self.__config.get('calculate.min_prices'),
                             max_set_size_diff_pct=self.__config.get('calculate.max_set_size_diff_pct'),
                             overlap_pct=self.__config.get('calculate.overlap_pct'),
                             max_p_value=self.__config.get('calculate.max_p_value'))
        self.SetStatusText("", 1)

        # Show calculated data
        self.__refresh_grid()

    def quit(self, event):
        # Close
        self.Close()

    def __refresh_grid(self):
        """
        Refreshes grid. Notifies if rows have been added or deleted.
        :return:
        """
        self.__log.debug(f"Refreshing grid. Timer running: {self.timer.IsRunning()}")

        # Update data
        self.table.data = self.__cor.filtered_coefficient_data.copy()

        # Format
        self.table.data.loc[:, 'Base Coefficient'] = self.table.data['Base Coefficient'].map('{:.5f}'.format)
        self.table.data.loc[:, 'Last Calculation'] = pd.to_datetime(self.table.data['Last Calculation'], utc=True)
        self.table.data.loc[:, 'Last Calculation'] = \
            self.table.data['Last Calculation'].dt.strftime('%d-%m-%y %H:%M:%S')

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

    def __monitor(self, event):
        # Check state of toggle button. If on, then start monitoring, else stop
        if self.__menu_item_monitor.IsChecked():
            self.__log.info("Starting monitoring for changes to coefficients.")
            self.SetStatusText("Monitoring", 0)
            self.__statusbar.SetBackgroundColour('green')
            self.__statusbar.Refresh()

            self.timer.Start(self.__config.get('monitor.interval')*1000)

            # Autosave filename
            filename = self.__opened_filename if self.__opened_filename is not None else 'autosave.cpd'

            # Build calculation params and start monitor
            calculation_params = [self.__config.get('monitor.calculations.long'),
                                  self.__config.get('monitor.calculations.medium'),
                                  self.__config.get('monitor.calculations.short')]

            self.__cor.start_monitor(interval=self.__config.get('monitor.interval'),
                                     calculation_params=calculation_params,
                                     cache_time=self.__config.get('monitor.tick_cache_time'),
                                     autosave=self.__config.get('monitor.autosave'),
                                     filename=filename)
        else:
            self.__log.info("Stopping monitoring.")
            self.SetStatusText("Not Monitoring", 0)
            self.__statusbar.SetBackgroundColour('lightgray')
            self.__statusbar.Refresh()
            self.timer.Stop()
            self.__cor.stop_monitor()

    def open_settings(self, event):
        """
        Opens the settings dialog
        :return:
        """
        settings_dialog = cfg.SettingsDialog(parent=self, exclude=['window'])
        res = settings_dialog.ShowModal()
        if res == wx.ID_OK:
            # Reload relevant parts of app
            restart_monitor_timer = False
            restart_gui_timer = False
            reload_correlations = False
            reload_logger = False
            reload_graph = False

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
                if setting.startswith('monitor.calculations'):
                    reload_graph = True

            # Now perform the actions
            if restart_monitor_timer:
                self.__log.info("Settings updated. Reloading monitoring timer.")
                self.__cor.stop_monitor()

                # Build calculation params and start monitor
                calculation_params = [self.__config.get('monitor.calculations.long'),
                                      self.__config.get('monitor.calculations.medium'),
                                      self.__config.get('monitor.calculations.short')]

                self.__cor.start_monitor(interval=self.__config.get('monitor.interval'),
                                         calculation_params=calculation_params,
                                         cache_time=self.__config.get('monitor.tick_cache_time'),
                                         autosave=self.__config.get('monitor.autosave'),
                                         filename=self.__opened_filename)

            if restart_gui_timer:
                self.__log.info("Settings updated. Restarting gui timer.")
                self.timer.Stop()
                self.timer.Start(self.__config.get('monitor.interval') * 1000)

            if reload_correlations:
                self.__log.info("Settings updated. Updating monitoring threshold and reloading grid.")
                self.__cor.monitoring_threshold = self.__config.get("monitor.monitoring_threshold")
                self.__refresh_grid()

            if reload_logger:
                self.__log.info("Settings updated. Reloading logger.")
                log_config = cfg.Config().get('logging')
                logging.config.dictConfig(log_config)

            if reload_graph:
                self.__log.info("Settings updated. Reloading graph.")
                if len(self.__selected_correlation) == 2:
                    self.show_graph(symbol1=self.__selected_correlation[0], symbol2=self.__selected_correlation[1])

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
        history_data_short = \
            self.__cor.get_coefficient_history({'Symbol 1': symbol1, 'Symbol 2': symbol2,
                                                'Timeframe': self.__config.get('monitor.calculations.short.from')})
        history_data_med = \
            self.__cor.get_coefficient_history({'Symbol 1': symbol1, 'Symbol 2': symbol2,
                                                'Timeframe': self.__config.get('monitor.calculations.medium.from')})
        history_data_long = \
            self.__cor.get_coefficient_history({'Symbol 1': symbol1, 'Symbol 2': symbol2,
                                                'Timeframe': self.__config.get('monitor.calculations.long.from')})
        # Display if we have any data
        self.__log.debug(f"Refreshing history graph {symbol1}:{symbol2}.")
        self.__graph.draw(prices=[symbol_1_price_data, symbol_2_price_data], ticks=[symbol_1_ticks, symbol_2_ticks],
                          history=[history_data_short, history_data_med, history_data_long], symbols=[symbol1, symbol2],
                          divergence_threshold=self.__cor.divergence_threshold,
                          monitor_inverse=self.__cor.monitor_inverse)

        # Un-hide and layout if hidden
        if not self.__graph.IsShown():
            self.__graph.Show()
            self.__main_sizer.Layout()

    def __timer_event(self, event):
        """
        Called on timer event. Refreshes grid and updates selected graph.
        :return:
        """
        self.__refresh_grid()
        if len(self.__selected_correlation) == 2:
            self.show_graph(symbol1=self.__selected_correlation[0], symbol2=self.__selected_correlation[1])

        # Set status message
        self.SetStatusText(f"Status updated at {self.__cor.get_last_calculation():%d-%b %H:%M:%S}.", 1)

    def __clear_history(self, event):
        """
        Clears the calculated coefficient history and associated price data
        :param event:
        :return:
        """
        # Clear the history
        self.__cor.clear_coefficient_history()

        # Reload graph if we have a coefficient selected
        self.__log.info("History cleared. Reloading graph.")
        if len(self.__selected_correlation) == 2:
            self.show_graph(symbol1=self.__selected_correlation[0], symbol2=self.__selected_correlation[1])

        # Reload the table
        self.__refresh_grid()


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
        self.divergence_threshold = cfg.Config().get('monitor.divergence_threshold')

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
        threshold = cfg.Config().get('monitor.divergence_threshold')
        if col in [MonitorFrame.COLUMN_STATUS]:
            # Is status one of interest
            value = self.GetValue(row, col)
            if value != "":
                if value in [cor.STATUS_DIVERGING]:
                    attr.SetBackgroundColour(wx.RED)
                elif value in [cor.STATUS_CONVERGING]:
                    attr.SetBackgroundColour(wx.GREEN)
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

        # Fig & canvas
        self.__fig = plt.figure()
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

    def draw(self, prices, ticks, history, symbols, divergence_threshold=None, monitor_inverse=False):
        """
        Plot the correlations.
        :param prices: Price data used to calculate base coefficient. List [Symbol1 Price Data, Symbol 2 Price Data]
        :param ticks: Ticks used to calculate last coefficient. List [Symbol1, Symbol2]
        :param history: Coefficient history data. List of data for one or more timeframes.
        :param symbols: Symbols. List [Symbol1, Symbol2]
        :param divergence_threshold: The divergence threshold. Will be plotted on the coefficients charts if specified.
        :param monitor_inverse: Are we monitoring inverse correlations. If so, a line for the inverse threshold will be
            plotted if the divergence threshold is specified.
        :return:
        """

        # Check what data we have available
        price_data_available = prices is not None and len(prices) == 2 and \
            prices[0] is not None and prices[1] is not None and len(prices[0]) > 0 and len(prices[1]) > 0
        tick_data_available = ticks is not None and len(ticks) == 2 and ticks[0] is not None and ticks[1] is not None \
            and len(ticks[0]) > 0 and len(ticks[1]) > 0
        history_data_available = history is not None and len(history) > 0
        symbols_selected = symbols is not None and len(symbols) == 2

        # Get all plots for history. History can contain multiple plots for different timeframes. They will all be
        # plotted on the same chart.
        times = []
        coefficients = []
        if history_data_available:
            for hist in history:
                times.append(hist['Date To'])
                coefficients.append(hist['Coefficient'])

        if symbols_selected:
            # Axis ranges
            if price_data_available:
                price_chart_date_range = [min(min(prices[0]['time']), min(prices[1]['time'])),
                                          max(max(prices[0]['time']), max(prices[1]['time']))]
            else:
                price_chart_date_range = [datetime.now() - timedelta(days=1), datetime.now()]

            if tick_data_available:
                tick_chart_date_range = [min(min(ticks[0]['time']), min(ticks[1]['time'])),
                                         max(max(ticks[0]['time']), max(ticks[1]['time']))]
            else:
                tick_chart_date_range = [datetime.now() - timedelta(days=1/48), datetime.now()]

            # First two charts. Data used to calculate base coefficient and data used to calculate latest coefficient.
            # Both charts will use 2 plots on a single axis and have different y ranges.
            titles = [f"Base Coefficient Price Data for {symbols[0]}:{symbols[1]}",
                      f"Coefficient Tick Data for {symbols[0]}:{symbols[1]}"]
            xlims = [price_chart_date_range, tick_chart_date_range]

            xdata = [[prices[0]['time'] if price_data_available else [],
                      prices[1]['time'] if price_data_available else []],
                     [ticks[0]['time'] if tick_data_available else [],
                      ticks[1]['time'] if tick_data_available else []]]

            ydata = [[prices[0]['close'] if price_data_available else [],
                      prices[1]['close'] if price_data_available else []],
                     [ticks[0]['ask'] if tick_data_available else [],
                      ticks[1]['ask'] if tick_data_available else []]]

            tick_labels = [prices[1]['time'] if price_data_available else [],
                           ticks[1]['time'] if tick_data_available else []]

            tick_formats = [self.__tick_fmt_date, self.__tick_fmt_time]

            # Clear the figure then redraw the 2 charts
            self.__fig.clf()
            for i in range(0, 2):
                # 2 axis. One for each symbol
                s1ax = self.__fig.add_subplot(3, 1, i+1)
                s2ax = s1ax.twinx()

                # Titles and axis labels
                s1ax.set_title(titles[i])
                s1ax.set_ylabel('Price')

                # X Limits
                s1ax.set_xlim(xlims[i])

                # Y Labels. Left for symbol1, right for symbol2
                colors = ['green', 'blue']
                s1ax.set_ylabel(f"{symbols[0]}", color=colors[0])
                s2ax.set_ylabel(f"{symbols[1]}", color=colors[1])

                # Plot both lines
                s1ax.plot(xdata[i][0], ydata[i][0], color=colors[0])
                s2ax.plot(xdata[i][1], ydata[i][1], color=colors[1])

                # Y tick colours
                s1ax.tick_params(axis='y', labelcolor=colors[0])
                s2ax.tick_params(axis='y', labelcolor=colors[1])

                # Ticks, labels and formats. Fixing xticks with FixedLocator but also using MaxNLocator to avoid
                # cramped x-labels
                if len(tick_labels[i]) > 0:
                    s1ax.xaxis.set_major_locator(mticker.MaxNLocator(10))
                    ticks_loc = s1ax.get_xticks().tolist()
                    s1ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
                    s1ax.set_xticklabels(ticks_loc)
                    if tick_formats[i] is not None:
                        s1ax.xaxis.set_major_formatter(tick_formats[i])
                    plt.setp(s1ax.xaxis.get_majorticklabels(), rotation=45)
                else:
                    s1ax.set_xticklabels([])

            # Third chart showing the coefficient history and the divergence threshold lines.
            ax = self.__fig.add_subplot(3, 1, 3)

            # Titles and axis labels
            ax.set_title(f"Coefficient History for {symbols[0]}:{symbols[1]}")
            ax.set_ylabel('Coefficient')

            # Y Limits. Coefficients range from -1 to 1
            ax.set_ylim([-1, 1])

            # Plot data if we have history data available
            if history_data_available:
                # Plot. There may be more than one set of data for chart. One for each coefficient date range. Convert
                # single data to list, then loop to plot
                xdata = times if isinstance(times, list) else [times, ]
                ydata = coefficients if isinstance(coefficients, list) else [coefficients, ]

                for i in range(0, len(xdata)):
                    ax.scatter(xdata[i], ydata[i], s=1)

                # Ticks, labels and formats. Fixing xticks with FixedLocator but also using MaxNLocator to avoid
                # cramped x-labels
                if len(times[0].array) > 0:
                    ax.xaxis.set_major_locator(mticker.MaxNLocator(10))
                    ticks_loc = ax.get_xticks().tolist()
                    ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
                    ax.set_xticklabels(ticks_loc)
                    ax.xaxis.set_major_formatter(self.__tick_fmt_time)
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
                else:
                    ax.set_xticklabels([])

                # Legend
                ax.legend([f"{cfg.Config().get('monitor.calculations.long.from')} Minutes",
                           f"{cfg.Config().get('monitor.calculations.medium.from')} Minutes",
                           f"{cfg.Config().get('monitor.calculations.short.from')} Minutes"])

                # Lines showing divergence threshold. 2 if we are monitoring inverse correlations.
                if divergence_threshold is not None:
                    ax.axhline(y=divergence_threshold, color="red", label='_nolegend_', linewidth=1)
                    if monitor_inverse:
                        ax.axhline(y=divergence_threshold * -1, color="red", label='_nolegend_', linewidth=1)

            # Layout with padding between charts
            self.__fig.tight_layout(pad=0.5)

        # Redraw canvas
        self.__canvas.draw()
