import abc
import logging
import pytz
import wx
import wxconfig as cfg

from datetime import datetime, timedelta

from mt5_correlation import correlation as cor


class CorrelationMDIFrame(wx.MDIParentFrame):
    """
    The MDI Frame window for the correlation monitoring application
    """
    # The correlation instance that calculates coefficients and monitors for divergence. Needs to be accessible to
    # child frames.
    cor = None

    __opened_filename = None  # So we can save to same file as we opened
    __log = None  # The logger
    __menu_item_monitor = None  # We need to store this menu item so that we can check if it is checked or not.

    def __init__(self):
        # Super
        wx.MDIParentFrame.__init__(self, parent=None, id=wx.ID_ANY, title="Divergence Monitor",
                                   pos=wx.Point(x=cfg.Config().get('window.x'), y=cfg.Config().get('window.y')),
                                   size=wx.Size(width=cfg.Config().get('window.width'),
                                                height=cfg.Config().get('window.height')),
                                   style=cfg.Config().get('window.style'))

        # Create logger
        self.__log = logging.getLogger(__name__)

        # Create correlation instance to maintain state of calculated coefficients. Set params from config
        self.cor = cor.Correlation(monitoring_threshold=cfg.Config().get("monitor.monitoring_threshold"),
                                   divergence_threshold=cfg.Config().get("monitor.divergence_threshold"),
                                   monitor_inverse=cfg.Config().get("monitor.monitor_inverse"))

        # Status bar. 2 fields, one for monitoring status and one for general status. On open, monitoring status is not
        # monitoring. SetBackgroundColour will change colour of both. Couldn't find a way to set on single field only.
        self.__statusbar = self.CreateStatusBar(2)
        self.__statusbar.SetStatusWidths([100, -1])
        self.SetStatusText("Not Monitoring", 0)

        # Create menu bar and bind menu items to methods
        self.menubar = wx.MenuBar()

        # File menu and items
        menu_file = wx.Menu()
        self.Bind(wx.EVT_MENU, self.__on_open_file, menu_file.Append(wx.ID_ANY, "&Open", "Open correlations file."))
        self.Bind(wx.EVT_MENU, self.__on_save_file, menu_file.Append(wx.ID_ANY, "Save", "Save correlations file."))
        self.Bind(wx.EVT_MENU, self.__on_save_file_as,
                  menu_file.Append(wx.ID_ANY, "Save As", "Save correlations file."))
        menu_file.AppendSeparator()
        self.Bind(wx.EVT_MENU, self.__on_open_settings,
                  menu_file.Append(wx.ID_ANY, "Settings", "Change application settings."))
        menu_file.AppendSeparator()
        self.Bind(wx.EVT_MENU, self.__on_exit, menu_file.Append(wx.ID_ANY, "Exit", "Close the application"))
        self.menubar.Append(menu_file, "&File")

        # Coefficient menu and items
        menu_coef = wx.Menu()
        self.Bind(wx.EVT_MENU, self.__on_calculate,
                  menu_coef.Append(wx.ID_ANY, "Calculate", "Calculate base coefficients."))
        self.__menu_item_monitor = menu_coef.Append(wx.ID_ANY, "Monitor",
                                                    "Monitor correlated pairs for changes to coefficient.",
                                                    kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, self.__on_monitor, self.__menu_item_monitor)
        menu_coef.AppendSeparator()
        self.Bind(wx.EVT_MENU, self.__on_clear,
                  menu_coef.Append(wx.ID_ANY, "Clear", "Clear coefficient and price history."))
        self.menubar.Append(menu_coef, "Coefficient")

        # View menu and items
        menu_view = wx.Menu()
        self.Bind(wx.EVT_MENU, self.__on_view_status, menu_view.Append(wx.ID_ANY, "Status",
                                                                       "View status of correlations."))
        self.Bind(wx.EVT_MENU, self.__on_view_diverged, menu_view.Append(wx.ID_ANY, "Diverged Symbols",
                                                                         "View diverged symbols."))
        self.menubar.Append(menu_view, "&View")

        # Set menu bar
        self.SetMenuBar(self.menubar)

        # Set up timer to refresh
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.__on_timer, self.timer)

        # Bind window close event
        self.Bind(wx.EVT_CLOSE, self.__on_close, self)

    def __on_close(self, event):
        """
        Window closing. Save coefficients and stop monitoring.
        :param event:
        :return:
        """
        # Save pos and size
        x, y = self.GetPosition()
        width, height = self.GetSize()
        cfg.Config().set('window.x', x)
        cfg.Config().set('window.y', y)
        cfg.Config().set('window.width', width)
        cfg.Config().set('window.height', height)

        # Style
        style = self.GetWindowStyle()
        cfg.Config().set('window.style', style)

        cfg.Config().save()

        # Stop monitoring
        self.cor.stop_monitor()

        # End
        event.Skip()

    def __on_open_file(self, evt):
        with wx.FileDialog(self, "Open Coefficients file", wildcard="cpd (*.cpd)|*.cpd",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # Load the file chosen by the user.
            self.__opened_filename = fileDialog.GetPath()

            self.SetStatusText(f"Loading file {self.__opened_filename}.", 1)
            self.cor.load(self.__opened_filename)

            # Show calculated data and refresh all opened frames
            self.__on_view_status(evt)
            self.__refresh()

            self.SetStatusText(f"File {self.__opened_filename} loaded.", 1)

    def __on_save_file(self, evt):
        self.SetStatusText(f"Saving file as {self.__opened_filename}", 1)

        if self.__opened_filename is None:
            self.__on_save_file_as(evt)
        else:
            self.cor.save(self.__opened_filename)

        self.SetStatusText(f"File saved as {self.__opened_filename}", 1)

    def __on_save_file_as(self, evt):
        with wx.FileDialog(self, "Save Coefficients file", wildcard="cpd (*.cpd)|*.cpd",
                           style=wx.FD_SAVE) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # Save the file and price data file, changing opened filename so next save writes to new file
            self.SetStatusText(f"Saving file as {self.__opened_filename}", 1)

            self.__opened_filename = fileDialog.GetPath()
            self.cor.save(self.__opened_filename)

            self.SetStatusText(f"File saved as {self.__opened_filename}", 1)

    def __on_open_settings(self, evt):
        settings_dialog = cfg.SettingsDialog(parent=self, exclude=['window'])
        res = settings_dialog.ShowModal()
        if res == wx.ID_OK:
            # Stop the monitor
            self.cor.stop_monitor()

            # Build calculation params and restart the monitor
            calculation_params = [cfg.Config().get('monitor.calculations.long'),
                                  cfg.Config().get('monitor.calculations.medium'),
                                  cfg.Config().get('monitor.calculations.short')]

            self.cor.start_monitor(interval=cfg.Config().get('monitor.interval'),
                                   calculation_params=calculation_params,
                                   cache_time=cfg.Config().get('monitor.tick_cache_time'),
                                   autosave=cfg.Config().get('monitor.autosave'),
                                   filename=self.__opened_filename)

            # Refresh all open child frames
            self.__refresh()

    def __on_exit(self, evt):
        # Close
        self.Close()

    def __on_calculate(self, evt):
        # set time zone to UTC to avoid local offset issues, and get from and to dates (a week ago to today)
        timezone = pytz.timezone("Etc/UTC")
        utc_to = datetime.now(tz=timezone)
        utc_from = utc_to - timedelta(days=cfg.Config().get('calculate.from.days'))

        # Calculate
        self.SetStatusText("Calculating coefficients.", 1)
        self.cor.calculate(date_from=utc_from, date_to=utc_to,
                           timeframe=cfg.Config().get('calculate.timeframe'),
                           min_prices=cfg.Config().get('calculate.min_prices'),
                           max_set_size_diff_pct=cfg.Config().get('calculate.max_set_size_diff_pct'),
                           overlap_pct=cfg.Config().get('calculate.overlap_pct'),
                           max_p_value=cfg.Config().get('calculate.max_p_value'))
        self.SetStatusText("", 1)

        # Show calculated data and refresh frames
        self.__on_view_status(evt)
        self.__refresh()

    def __on_monitor(self, evt):
        # Check state of toggle menu. If on, then start monitoring, else stop
        if self.__menu_item_monitor.IsChecked():
            self.__log.info("Starting monitoring for changes to coefficients.")
            self.SetStatusText("Monitoring", 0)
            self.__statusbar.SetBackgroundColour('green')
            self.__statusbar.Refresh()

            self.timer.Start(cfg.Config().get('monitor.interval') * 1000)

            # Autosave filename
            filename = self.__opened_filename if self.__opened_filename is not None else 'autosave.cpd'

            # Build calculation params and start monitor
            calculation_params = [cfg.Config().get('monitor.calculations.long'),
                                  cfg.Config().get('monitor.calculations.medium'),
                                  cfg.Config().get('monitor.calculations.short')]

            self.cor.start_monitor(interval=cfg.Config().get('monitor.interval'),
                                   calculation_params=calculation_params,
                                   cache_time=cfg.Config().get('monitor.tick_cache_time'),
                                   autosave=cfg.Config().get('monitor.autosave'),
                                   filename=filename)
        else:
            self.__log.info("Stopping monitoring.")
            self.SetStatusText("Not Monitoring", 0)
            self.__statusbar.SetBackgroundColour('lightgray')
            self.__statusbar.Refresh()
            self.timer.Stop()
            self.cor.stop_monitor()

    def __on_clear(self, evt):
        # Clear the history
        self.cor.clear_coefficient_history()

        # Refresh opened child frames
        self.__refresh()

    def __on_timer(self, evt):
        # Refresh opened child frames
        self.__refresh()

        # Set status message
        self.SetStatusText(f"Status updated at {self.cor.get_last_calculation():%d-%b %H:%M:%S}.", 1)

    def __on_view_status(self, evt):
        from mt5_correlation.gui.mdi_child_status import MDIChildStatus

        # Only open if not already open. If already open then raise to top.
        opened_instance = None
        for child in self.GetChildren():
            if isinstance(child, MDIChildStatus):
                opened_instance = child

        if opened_instance is None:
            MDIChildStatus(parent=self).Show(True)
        else:
            opened_instance.Raise()

    def __on_view_diverged(self, evt):
        from mt5_correlation.gui.mdi_child_diverged_symbols import MDIChildDivergedSymbols

        # Only open if not already open. If already open then raise to top.
        opened_instance = None
        for child in self.GetChildren():
            if isinstance(child, MDIChildDivergedSymbols):
                opened_instance = child

        if opened_instance is None:
            MDIChildDivergedSymbols(parent=self).Show(True)
        else:
            opened_instance.Raise()

    def __refresh(self):
        """
        Refresh all open child frames
        :return:
        """
        children = self.GetChildren()

        for child in children:
            if isinstance(child, CorrelationMDIChild):
                child.refresh()
            elif isinstance(child, wx.StatusBar):
                # Ignore
                pass
            else:
                raise Exception(f"MDI Child for application must implement CorrelationMDIChild.")


class CorrelationMDIChild(wx.MDIChildFrame):
    """
    Interface for all MDI Children supported by the MDIParent
    """

    @abc.abstractmethod
    def refresh(self):
        """
        Must be implemented. Refreshes the content. Called by MDIParents __refresh method
        :return:
        """
        raise NotImplementedError
