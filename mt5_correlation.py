"""
Application to monitor previously correlated symbol pairs for correlation divergence.
"""
import definitions
import logging.config
from mt5_correlation.gui import CorrelationMDIFrame
import wxconfig as cfg
import wx
import wx.lib.mixins.inspection as wit


class InspectionApp(wx.App, wit.InspectionMixin):
    # Override app to use inspection.
    def OnInit(self):
        self.Init()  # initialize the inspection tool
        return True


if __name__ == "__main__":
    # Load the config
    cfg.Config().load(fr"{definitions.ROOT_DIR}\config.yaml", meta=fr"{definitions.ROOT_DIR}\configmeta.yaml")

    # Get logging config and configure the logger
    log_config = cfg.Config().get('logging')
    logging.config.dictConfig(log_config)

    # Do we have inspection turned on. Create correct version of app
    inspection = cfg.Config().get('developer.inspection')
    if inspection:
        app = InspectionApp()
    else:
        app = wx.App(False)

    # Start the app
    frame = CorrelationMDIFrame()
    frame.Show()
    app.MainLoop()
