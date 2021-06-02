import definitions
import wx
import wx.html

import mt5_correlation.gui.mdi as mdi


class MDIChildLog(mdi.CorrelationMDIChild):
    """
    Shows the debug.log file
    """

    __log_window = None  # Widget to display log file in

    def __init__(self, parent):
        # Super
        mdi.CorrelationMDIChild.__init__(self, parent=parent, id=wx.ID_ANY, pos=wx.DefaultPosition, title="Log",
                                         size=wx.Size(width=800, height=200),
                                         style=wx.DEFAULT_FRAME_STYLE)

        # Panel and sizer for help file
        panel = wx.Panel(self, wx.ID_ANY)
        sizer = wx.BoxSizer()
        panel.SetSizer(sizer)

        # Log file window
        self.__log_window = wx.TextCtrl(parent=panel, id=wx.ID_ANY, style=wx.HSCROLL | wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(self.__log_window, 1, wx.ALL | wx.EXPAND)

        # Refresh to populate
        self.refresh()

    def refresh(self):
        """
        Refresh the log file
        :return:
        """
        # Load the help file
        self.__log_window.LoadFile(definitions.LOG_FILE)

        # Scroll to bottom
        self.__log_window.SetInsertionPoint(-1)

