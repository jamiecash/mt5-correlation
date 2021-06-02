import logging
import matplotlib.dates
import matplotlib.pylab as pl
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as mp
import numpy as np
import wx
import wx.lib.scrolledpanel as scrolled
import wxconfig as cfg

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

    # Panel
    __panel = None

    # Graph Canvas and Figure
    __canvas = None
    __fig = None

    # Colors for graph lines
    __colours = matplotlib.cm.get_cmap(cfg.Config().get("charts.colormap")).colors

    def __init__(self, parent, **kwargs):
        # Super
        wx.MDIChildFrame.__init__(self, parent=parent, id=wx.ID_ANY,
                                  title=f"Divergence Graph for {kwargs['symbol']}")

        # Create logger
        self.__log = logging.getLogger(__name__)

        # Store the symbol
        self.symbol = kwargs['symbol']

        # Create panel and sizer
        self.__panel = scrolled.ScrolledPanel(self, wx.ID_ANY)
        sizer = wx.BoxSizer()
        self.__panel.SetSizer(sizer)

        # Create figure and canvas. Add canvas to sizer
        self.__fig = plt.Figure()
        self.__canvas = FigureCanvas(self.__panel, wx.ID_ANY, self.__fig)
        self.__panel.GetSizer().Add(self.__canvas, 1, wx.ALL | wx.EXPAND)

        # Setup scrolling
        self.__panel.SetupScrolling()

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
        if self.symbol in other_symbols:
            other_symbols.remove(self.symbol)

        # Get the tick data for base symbols and other symbols
        symbol_tick_data = self.GetMDIParent().cor.get_ticks(self.symbol, cache_only=True)
        other_tick_data = []
        for symbol in other_symbols:
            tick_data = self.GetMDIParent().cor.get_ticks(symbol, cache_only=True)
            other_tick_data.append(tick_data)

        # We will clear the figure and create new axis on every refresh as the shape will change on refresh if symbols
        # change
        self.__fig.clear()
        axs = self.__fig.add_subplot(111)  # Axis to fill canvas

        # Set title
        axs.set_title(f"Price Data for {self.symbol}:{other_symbols}".replace("'", ""))

        # Set Y Labels and tick colours for symbol. This will be set for other symbols on plot
        for i in range(0, 2):
            axs.set_ylabel(f"{self.symbol}", color=self.__colours[0], labelpad=10)
            axs.tick_params(axis='y', labelcolor=self.__colours[0])

        # Store the lines for the legend
        lines = []

        # Plot tick data for the base symbol. Store line and label.
        line = axs.plot(symbol_tick_data['time'], symbol_tick_data['ask'], color=self.__colours[0],
                        label=self.symbol)[0]
        lines.append(line)

        # Plot for the other symbols on new axes.
        spinepos = 0  # Position of spine. Starting at 2nd plot, will be increased for every plot.
        for i in range(0, len(other_tick_data)):
            other_axis = axs.twinx()

            # Move spine if we are not on first plot
            if i > 0:
                spinepos += 1.15
                other_axis.spines['right'].set_position(("axes", spinepos))

                # The frame is off, so line of detached spine is invisible. Activate frame and then make patch and
                # spines invisible
                other_axis.set_frame_on(True)
                other_axis.patch.set_visible(False)
                for sp in other_axis.spines.values():
                    sp.set_visible(False)

                # Show the right spline
                other_axis.spines['right'].set_visible(True)

            # Plot. We will use a lighter line for the other symbols. Store line.
            line = other_axis.plot(other_tick_data[i]['time'], other_tick_data[i]['ask'], color=self.__colours[i + 1],
                                   label=other_symbols[i], linestyle='solid', linewidth=0.5)[0]
            lines.append(line)

            # Set y label, label colour and tick colour
            other_axis.set_ylabel(f"{other_symbols[i]}", color=self.__colours[i + 1], labelpad=10)
            other_axis.tick_params(axis='y', labelcolor=self.__colours[i + 1])

        # Ticks, labels and formats. Fixing xticks with FixedLocator but also using MaxNLocator to avoid
        # cramped x-labels
        if len(symbol_tick_data['time']) > 0:
            axs.xaxis.set_major_locator(mticker.MaxNLocator(10))
            ticks_loc = axs.get_xticks().tolist()
            axs.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
            axs.set_xticklabels(ticks_loc)
            axs.xaxis.set_major_formatter(self.__tick_fmt_time)
            plt.setp(axs.xaxis.get_majorticklabels(), rotation=45)

        # Legend
        # axs.legend(lines, [line.get_label() for line in lines], loc=0)

        # Tight layout
        self.__fig.tight_layout()

        # Redraw canvas
        self.__canvas.draw()

    def __del__(self):
        # Close all plots
        plt.close('all')
