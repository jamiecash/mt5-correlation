import logging
import matplotlib.dates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import wx
import wxconfig as cfg
import wx.lib.scrolledpanel as scrolled

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas

import mt5_correlation.gui.mdi as mdi


class MDIChildCorrelationGraph(mdi.CorrelationMDIChild):
    """
    Shows the graphs for the specified correlation
    """

    symbols = None  # Symbols for correlation. Public as we use to check if window for the symbol pair is already open.

    # Date formats for graphs
    __tick_fmt_date = matplotlib.dates.DateFormatter('%d-%b')
    __tick_fmt_time = matplotlib.dates.DateFormatter('%H:%M:%S')

    # Colors for graph lines fro symbol1 and symbol2
    __colours = ['green', 'blue']

    # Fig, axes and canvas
    __fig = None
    __axs = None
    __canvas = None

    def __init__(self, parent, symbol1, symbol2):
        # Super
        wx.MDIChildFrame.__init__(self, parent=parent, id=wx.ID_ANY,
                                  title=f"Correlation Status for {symbol1}:{symbol2}")

        # Create logger
        self.__log = logging.getLogger(__name__)

        # Store the symbols
        self.symbols = [symbol1, symbol2]

        # We will freeze this frame and thaw once constructed to avoid flicker.
        self.Freeze()

        # Draw the empty graphs. We will populate with data in refresh. We will have 3 charts:
        #   1) Data used to calculate base coefficient for both symbols (2 lines on chart);
        #   2) Data used to calculate latest coefficient for both symbols (2 lines on chart); and
        #   3) Coefficient history and the divergence threshold lines

        # Create fig and 3 axes.
        self.__fig, self.__axs = plt.subplots(3)

        # Create additional axis for second line on charts 1 & 2
        self.__s2axs = [self.__axs[0].twinx(), self.__axs[1].twinx()]

        # Set titles
        self.__axs[0].set_title(f"Base Coefficient Price Data for {self.symbols[0]}:{self.symbols[1]}")
        self.__axs[1].set_title(f"Coefficient Tick Data for {self.symbols[0]}:{self.symbols[1]}")
        self.__axs[2].set_title(f"Coefficient History for {self.symbols[0]}:{self.symbols[1]}")

        # Set Y Labels and tick colours for charts 1 & 2. Left for symbol1, right for symbol2
        for i in range(0, 2):
            self.__axs[i].set_ylabel(f"{self.symbols[0]}", color=self.__colours[0])
            self.__axs[i].tick_params(axis='y', labelcolor=self.__colours[0])
            self.__s2axs[i].set_ylabel(f"{self.symbols[1]}", color=self.__colours[1])
            self.__s2axs[i].tick_params(axis='y', labelcolor=self.__colours[1])

        # Set Y label and limits for 3rd chart. Limits will be coefficients range from -1 to 1
        self.__axs[2].set_ylabel('Coefficient')
        self.__axs[2].set_ylim([-1, 1])

        # Layout with padding between charts
        self.__fig.tight_layout(pad=0.5)

        # Create panel and sizer. This will provide scrollbar
        panel = scrolled.ScrolledPanel(self, wx.ID_ANY)
        sizer = wx.BoxSizer()
        panel.SetSizer(sizer)

        # Add fig to canvas and canvas to sizer. Thaw window to update
        self.__canvas = FigureCanvas(panel, wx.ID_ANY, self.__fig)
        sizer.Add(self.__canvas, 1, wx.ALL | wx.EXPAND)
        self.Thaw()

        # Setup scrolling
        panel.SetupScrolling()

        # Refresh to show content
        self.refresh()

    def refresh(self):
        """
        Refresh the graph
        :return:
        """
        # Get the price data for the base coefficient calculation, tick data that was used to calculate last
        # coefficient and  and the coefficient history data
        price_data = [self.GetMDIParent().cor.get_price_data(self.symbols[0]),
                      self.GetMDIParent().cor.get_price_data(self.symbols[1])]

        tick_data = [self.GetMDIParent().cor.get_ticks(self.symbols[0], cache_only=True),
                     self.GetMDIParent().cor.get_ticks(self.symbols[1], cache_only=True)]

        history_data = []
        for timeframe in cfg.Config().get('monitor.calculations'):
            frm = cfg.Config().get(f'monitor.calculations.{timeframe}.from')
            history_data.append(self.GetMDIParent().cor.get_coefficient_history(
                {'Symbol 1': self.symbols[0], 'Symbol 2': self.symbols[1], 'Timeframe': frm}))

        # Check what data we have available
        price_data_available = price_data is not None and len(price_data) == 2 and price_data[0] is not None and \
            price_data[1] is not None and len(price_data[0]) > 0 and len(price_data[1]) > 0

        tick_data_available = tick_data is not None and len(tick_data) == 2 and tick_data[0] is not None and \
            tick_data[1] is not None and len(tick_data[0]) > 0 and len(tick_data[1]) > 0

        history_data_available = history_data is not None and len(history_data) > 0

        # Get all plots for coefficient history. History can contain multiple plots for different timeframes. They
        # will all be plotted on the same chart.
        times = []
        coefficients = []
        if history_data_available:
            for hist in history_data:
                times.append(hist['Date To'])
                coefficients.append(hist['Coefficient'])

        # Update graphs where we have data available
        if price_data_available:
            # Update range and ticks
            xrange = [min(min(price_data[0]['time']), min(price_data[1]['time'])),
                      max(max(price_data[0]['time']), max(price_data[1]['time']))]
            self.__axs[0].set_xlim(xrange)

            # Plot both lines
            self.__axs[0].plot(price_data[0]['time'], price_data[0]['close'],
                               color=self.__colours[0])
            self.__s2axs[0].plot(price_data[1]['time'], price_data[1]['close'],
                                 color=self.__colours[1])

            # Ticks, labels and formats. Fixing xticks with FixedLocator but also using MaxNLocator to avoid
            # cramped x-labels
            if len(price_data[0]['time']) > 0:
                self.__axs[0].xaxis.set_major_locator(mticker.MaxNLocator(10))
                ticks_loc = self.__axs[0].get_xticks().tolist()
                self.__axs[0].xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
                self.__axs[0].set_xticklabels(ticks_loc)
                self.__axs[0].xaxis.set_major_formatter(self.__tick_fmt_date)
                plt.setp(self.__axs[0].xaxis.get_majorticklabels(), rotation=45)

        if tick_data_available:
            # Update range and ticks
            xrange = [min(min(tick_data[0]['time']), min(tick_data[1]['time'])),
                      max(max(tick_data[0]['time']), max(tick_data[1]['time']))]
            self.__axs[1].set_xlim(xrange)

            # Plot both lines
            self.__axs[1].plot(tick_data[0]['time'], tick_data[0]['ask'],
                               color=self.__colours[0])
            self.__s2axs[1].plot(tick_data[1]['time'], tick_data[1]['ask'],
                                 color=self.__colours[1])

            if len(tick_data[0]['time']) > 0:
                self.__axs[1].xaxis.set_major_locator(mticker.MaxNLocator(10))
                ticks_loc = self.__axs[1].get_xticks().tolist()
                self.__axs[1].xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
                self.__axs[1].set_xticklabels(ticks_loc)
                self.__axs[1].xaxis.set_major_formatter(self.__tick_fmt_time)
                plt.setp(self.__axs[1].xaxis.get_majorticklabels(), rotation=45)

        if history_data_available:
            # Plot. There may be more than one set of data for chart. One for each coefficient date range. Convert
            # single data to list, then loop to plot
            xdata = times if isinstance(times, list) else [times, ]
            ydata = coefficients if isinstance(coefficients, list) else [coefficients, ]

            for i in range(0, len(xdata)):
                self.__axs[2].scatter(xdata[i], ydata[i], s=1)

            # Ticks, labels and formats. Fixing xticks with FixedLocator but also using MaxNLocator to avoid
            # cramped x-labels
            if len(times[0].array) > 0:
                self.__axs[2].xaxis.set_major_locator(mticker.MaxNLocator(10))
                ticks_loc = self.__axs[2].get_xticks().tolist()
                self.__axs[2].xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
                self.__axs[2].set_xticklabels(ticks_loc)
                self.__axs[2].xaxis.set_major_formatter(self.__tick_fmt_time)
                plt.setp(self.__axs[2].xaxis.get_majorticklabels(), rotation=45)

                # Legend
                self.__axs[2].legend([f"{cfg.Config().get('monitor.calculations.long.from')} Minutes",
                                      f"{cfg.Config().get('monitor.calculations.medium.from')} Minutes",
                                      f"{cfg.Config().get('monitor.calculations.short.from')} Minutes"])

                # Lines showing divergence threshold. 2 if we are monitoring inverse correlations.
                divergence_threshold = self.GetMDIParent().cor.divergence_threshold
                monitor_inverse = self.GetMDIParent().cor.monitor_inverse

                if divergence_threshold is not None:
                    self.__axs[2].axhline(y=divergence_threshold, color="red", label='_nolegend_', linewidth=1)
                    if monitor_inverse:
                        self.__axs[2].axhline(y=divergence_threshold * -1, color="red", label='_nolegend_', linewidth=1)

        # Redraw canvas
        self.__canvas.draw()

    def __del__(self):
        # Close all plots
        plt.close('all')
