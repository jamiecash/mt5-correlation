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
    # Configure the logger
    with open(fr'{definitions.ROOT_DIR}\logging_conf.yaml', 'rt') as file:
        config = yaml.safe_load(file.read())
        logging.config.dictConfig(config)

    # Load the config
    config = Config.instance()
    config.load(fr"{definitions.ROOT_DIR}\config.yaml")

    # Start the app
    app = wx.App(False)
    frame = MonitorFrame(None, wx.ID_ANY, "")
    frame.Show()
    app.MainLoop()
