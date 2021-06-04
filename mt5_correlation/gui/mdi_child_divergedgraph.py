import logging
import matplotlib.dates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import wx
import wx.lib.scrolledpanel as scrolled
import wxconfig as cfg

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from mpl_toolkits.axes_grid1 import host_subplot
from mpl_toolkits import axisartist

import mt5_correlation.gui.mdi as mdi
from mt5_correlation import correlation as cor


class MDIChildDivergedGraph(mdi.CorrelationMDIChild):
    """
    Shows the graphs for the specified correlation
    """

    symbol = None  # Symbol to chart divergence for. Public as we use to check if window for the symbol is already open.

    # Logger
    __log = None

    # Date formats for graphs
    __tick_fmt_date = matplotlib.dates.DateFormatter('%d-%b')
    __tick_fmt_time = matplotlib.dates.DateFormatter('%H:%M:%S')

    # Graph Canvas
    __canvas = None

    # Colors for graph lines
    __colours = matplotlib.cm.get_cmap(cfg.Config().get("charts.colormap")).colors

    # We will store the other symbols last plotted. This will save us rebuilding teh figure if teh symbols haven't
    # changed.
    __other_symbols = None

    def __init__(self, parent, **kwargs):
        # Super
        wx.MDIChildFrame.__init__(self, parent=parent, id=wx.ID_ANY,
                                  title=f"Divergence Graph for {kwargs['symbol']}")

        # Create logger
        self.__log = logging.getLogger(__name__)

        # Store the symbol
        self.symbol = kwargs['symbol']

        # Create panel and sizer
        panel = scrolled.ScrolledPanel(self, wx.ID_ANY)
        sizer = wx.BoxSizer()
        panel.SetSizer(sizer)

        # Create figure and canvas. Add canvas to sizer
        self.__canvas = FigureCanvas(panel, wx.ID_ANY, plt.figure())
        panel.GetSizer().Add(self.__canvas, 1, wx.ALL | wx.EXPAND)
        panel.SetupScrolling()

        # Refresh to show content
        self.refresh()

    def refresh(self):
        """
        Refresh the graph
        :return:
        """

        # Get tick data for base symbol
        symbol_tick_data = self.GetMDIParent().cor.get_ticks(self.symbol, cache_only=True)

        # Get the other symbols and their tick data
        other_symbols_data = self.__get_other_symbols_data()

        # Delete all axes from the figure. They will need to be recreated as the symbols may be different
        for axes in self.__canvas.figure.axes:
            axes.remove()

        # Plot for all other symbols
        num_subplots = 1 if len(other_symbols_data.keys()) == 0 else len(other_symbols_data.keys())
        plotnum = 1
        axs = []  # Store the axes for sharing x axis
        for other_symbol in other_symbols_data:
            axs.append(self.__canvas.figure.add_subplot(num_subplots, 1, plotnum))
            self.__plot(axes=axs[-1], base_symbol=self.symbol, other_symbol=other_symbol,
                        base_symbol_data=symbol_tick_data, other_symbol_data=other_symbols_data[other_symbol])

            # Next plot
            plotnum += 1

        # Share x axis of the last axes with all the others
        self.__share_xaxis(axs)

        # Redraw canvas
        self.__canvas.figure.tight_layout(pad=0.5)
        self.__canvas.draw()

    def __get_other_symbols_data(self):
        """
        Gets the data required for the graphs
        :param self:
        :return: dict of other symbols their tick data
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

        # Get the tick data other symbols and add to dict
        other_tick_data = {}
        for symbol in other_symbols:
            tick_data = self.GetMDIParent().cor.get_ticks(symbol, cache_only=True)
            other_tick_data[symbol] = tick_data

        return other_tick_data

    def __plot(self, axes, base_symbol, other_symbol, base_symbol_data, other_symbol_data):
        """
        Plots the data on the axes
        :param axes: The subplot to plot onto
        :param base_symbol
        :param other_symbol:
        """
        # Create the other axes. Will need an axes for the base symbol data and another for the other symbol data
        other_axes = axes.twinx()

        # Set plot title and axis labels
        axes.set_title(f"Tick Data for {base_symbol}:{other_symbol}")
        axes.set_ylabel(base_symbol, color=self.__colours[0], labelpad=10)
        other_axes.set_ylabel(other_symbol, color=self.__colours[1], labelpad=10)

        # Set the tick and axis colors
        self.__set_axes_color(axes, self.__colours[0], 'left')
        self.__set_axes_color(other_axes, self.__colours[1], 'right')

        # Plot both lines
        axes.plot(base_symbol_data['time'], base_symbol_data['ask'], color=self.__colours[0])
        other_axes.plot(other_symbol_data['time'], other_symbol_data['ask'], color=self.__colours[1])

    @staticmethod
    def __set_axes_color(axes, color, axis_loc='right'):
        """
        Set the color for the axes, including axis line, ticks and tick labels
        :param axes: The axes to set color for.
        :param color: The color to set to
        :param axis_loc: The location of the axis, label and ticks. Either left for base symbol or right for others
        :return:
        """
        # Change the color for the axis line, ticks and tick labels
        axes.spines[axis_loc].set_color(color)
        axes.tick_params(axis='y', colors=color)

    def __share_xaxis(self, axs):
        """
        Share the xaxis of the last axes with all other axes. Remove axis tick labels for all but the last. Format axis
        tick labels for the last.
        :param axs:
        :return:
        """
        if len(axs) > 0:
            last_ax = axs[-1]
            for ax in axs:
                # If we are not on the last one, share and hide tick labels. If we are on the last one, format tick
                # labels.
                if ax != last_ax:
                    ax.sharex(last_ax)
                    plt.setp(ax.xaxis.get_majorticklabels(), visible=False)
                else:
                    # Ticks, labels and formats. Fixing xticks with FixedLocator but also using MaxNLocator to avoid
                    # cramped x-labels
                    ax.xaxis.set_major_locator(mticker.MaxNLocator(10))
                    ticks_loc = ax.get_xticks().tolist()
                    ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
                    ax.set_xticklabels(ticks_loc)
                    ax.xaxis.set_major_formatter(self.__tick_fmt_time)
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    def __del__(self):
        # Close all plots
        plt.close('all')
