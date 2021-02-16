"""
Application to monitor previously correlated symbol pairs for correlation divergence.
"""
import definitions
import yaml
import logging.config
from mt5_correlation.gui import MonitorFrame
from mt5_correlation.config import Config
import wx

if __name__ == "__main__":
    # Load the config
    Config().load(fr"{definitions.ROOT_DIR}\config.yaml")

    # Get logging config and configure the logger
    log_config = Config().get('logging')
    logging.config.dictConfig(log_config)

    # Start the app
    app = wx.App(False)
    frame = MonitorFrame()
    frame.Show()
    app.MainLoop()
