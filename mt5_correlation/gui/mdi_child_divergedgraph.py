import logging
import matplotlib.dates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import wx
import wxconfig as cfg
import wx.lib.scrolledpanel as scrolled

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas

import mt5_correlation.gui.mdi as mdi
from mt5_correlation import correlation as cor


class MDIChildDivergedGraph(mdi.CorrelationMDIChild):
    """
    Shows the graphs for the specified correlation
    """

    symbol = None  # Symbol to chart divergence for. Public as we use to check if window for the symbol is already open.

    # Date formats for graphs
    __tick_fmt_date = matplotlib.dates.DateFormatter('%d-%b')
    __tick_fmt_time = matplotlib.dates.DateFormatter('%H:%M:%S')

    # Fig, axes and canvas
    __fig = None
    __axs = None
    __canvas = None

    # Colors for graph lines
    __colours = ['red', 'green', 'blue', 'pink', 'purple', 'black', 'yellow', 'lightblue']

    def __init__(self, parent, **kwargs):
        # Super
        wx.MDIChildFrame.__init__(self, parent=parent, id=wx.ID_ANY,
                                  title=f"Divergence Graph for {kwargs['symbol']}")

        # Create logger
        self.__log = logging.getLogger(__name__)

        # Store the symbol
        self.symbol = kwargs['symbol']

        # We will freeze this frame and thaw once constructed to avoid flicker.
        self.Freeze()

        # Draw the empty graph. We will populate with data in refresh.

        # Create fig and 1 axes.
        self.__fig, self.__axs = plt.subplots(1)

        # Set title
        self.__axs.set_title(f"Price Data for {self.symbol} vs Previously Correlated Symbols")

        # Set Y Labels and tick colours for symbol. This will be set for other symbols on plot
        for i in range(0, 2):
            self.__axs.set_ylabel(f"{self.symbol}", color=self.__colours[0], labelpad=10)
            self.__axs.tick_params(axis='y', labelcolor=self.__colours[0])

        # Hack to stop xaxis dropping outside of window
        self.__axs.set_xlabel(" ", labelpad=10)

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

        # Get the symbols that this one has diverged against.
        data = self.GetMDIParent().cor.filtered_coefficient_data
        filtered_data = data.loc[(
                                         (data['Status'] == cor.STATUS_DIVERGED) |
                                         (data['Status'] == cor.STATUS_DIVERGING) |
                                         (data['Status'] == cor.STATUS_CONVERGING)
                                 ) &
                                 (
                                        (data['Symbol 1'] == self.symbol) |
                                        (data['Symbol 2'] == self.symbol)
                                )]

        # Get all symbols and remove the base one. We will need to ensure that this is first in the list
        other_symbols = list(filtered_data['Symbol 1'].append(filtered_data['Symbol 2']).drop_duplicates())
        other_symbols.remove(self.symbol)

        # Get the tick data for base symbols and other symbols
        symbol_tick_data = self.GetMDIParent().cor.get_ticks(self.symbol, cache_only=True)
        other_tick_data = []
        for symbol in other_symbols:
            tick_data = self.GetMDIParent().cor.get_ticks(symbol, cache_only=True)
            other_tick_data.append(tick_data)

        # Plot tick data for the base symbol
        self.__axs.plot(symbol_tick_data['time'], symbol_tick_data['ask'], color=self.__colours[0], label=self.symbol)

        # Plot for the other symbols on new axes
        for i in range(0, len(other_tick_data)):
            new_ax = self.__axs.twinx()
            new_ax.plot(other_tick_data[i]['time'], other_tick_data[i]['ask'], label=other_symbols[i],
                        color=self.__colours[i+1])
            new_ax.set_ylabel(f"{other_symbols[i]}", color=self.__colours[i+1], labelpad=10)
            new_ax.tick_params(axis='y', labelcolor=self.__colours[i+1])

        # Ticks, labels and formats. Fixing xticks with FixedLocator but also using MaxNLocator to avoid
        # cramped x-labels
        if len(symbol_tick_data['time']) > 0:
            self.__axs.xaxis.set_major_locator(mticker.MaxNLocator(10))
            ticks_loc = self.__axs.get_xticks().tolist()
            self.__axs.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
            self.__axs.set_xticklabels(ticks_loc)
            self.__axs.xaxis.set_major_formatter(self.__tick_fmt_time)
            plt.setp(self.__axs.xaxis.get_majorticklabels(), rotation=45)

        # Legend
        #self.__axs.legend([self.symbol, ] + other_symbols)

        # Redraw canvas
        self.__canvas.draw()

    def __del__(self):
        # Close all plots
        plt.close('all')
