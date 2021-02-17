"""
Application to monitor previously correlated symbol pairs for correlation divergence.
"""
import definitions
import logging.config
from mt5_correlation.gui import MonitorFrame
from mt5_correlation.config import Config
import wx
import wx.lib.mixins.inspection as wit


class CorrelationMonitorApp(wx.App, wit.InspectionMixin):
    # Override app to use inspection.
    # TODO Remove wit.InspectionMixin from overrides when live.
    def OnInit(self):
        self.Init()  # initialize the inspection tool
        return True


if __name__ == "__main__":
    # Load the config
    Config().load(fr"{definitions.ROOT_DIR}\config.yaml")

    # Get logging config and configure the logger
    log_config = Config().get('logging')
    logging.config.dictConfig(log_config)

    # Start the app
    app = CorrelationMonitorApp()
    frame = MonitorFrame()
    frame.Show()
    app.MainLoop()
