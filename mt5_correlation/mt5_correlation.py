import math
import pandas as pd
import MetaTrader5 as mt5
import logging
from scipy.stats.stats import pearsonr


class MT5Correlation:
    """
    A class to connect to MetaTrader 5 and calculate correlation coefficients between all pairs of symbols in MarketView
    """

    def __init__(self):
        # Connect to MetaTrader5. Opens if not already open.

        # Logger
        self.log = logging.getLogger(__name__)

        # Open MT5 and log error if it could not open
        if not mt5.initialize():
            self.log.error("initialize() failed")
            mt5.shutdown()

        # Print connection status
        self.log.debug(mt5.terminal_info())

        # Print data on MetaTrader 5 version
        self.log.debug(mt5.version())

    def __del__(self):
        # shut down connection to the MetaTrader 5 terminal
        mt5.shutdown()

    def get_symbols(self):
        """
        Gets list of symbols open in MT5 market watch.
        :return: list of symbols
        """
        # Iterate symbols and get those in market watch.
        symbols = mt5.symbols_get()
        selected_symbols = []
        for symbol in symbols:
            if symbol.visible:
                selected_symbols.append(symbol)

        # Log symbol counts
        total_symbols = mt5.symbols_total()
        num_selected_symbols = len(selected_symbols)
        self.log.info(f"{num_selected_symbols} of {total_symbols} available symbols in Market Watch.")

        return selected_symbols

    def get_prices(self, symbol, from_date, to_date):
        """
        Gets the 1 weeks of M15 OHLC price data for the specified symbol.
        :param symbol: The MT5 symbol to get the price data for
        :param from_date: Date from when to retrieve data
        :param to_date: Date where to receive data to
        :return: Price data for symbol as dataframe
        """
        # Get prices from MT5
        prices = mt5.copy_rates_range(symbol.name, mt5.TIMEFRAME_M15, from_date, to_date)
        self.log.info(f"{len(prices)} prices retrieved for {symbol.name}.")

        # Create dataframe from data and convert time in seconds to datetime format
        prices_dataframe = pd.DataFrame(prices)
        prices_dataframe['time'] = pd.to_datetime(prices_dataframe['time'], unit='s')

        return prices_dataframe

    def calculate_coefficient(self, symbol1_prices, symbol2_prices):
        """
        Calculates the correlation coefficient between two sets of price data. Uses close price.

        :param symbol1_prices:
        :param symbol2_prices:
        :return: correlation coefficient, or None if coefficient could not be calculated.
        """
        # Calculate size of intersection and determine if prices for symbols have enough overlapping timestamps for
        # correlation coefficient calculation to be meaningful. Is the smallest set at least 90% of the size of the
        # largest set and is the overlap set size at least 90% the size of the smallest set?
        coefficient = None

        intersect_dates = (set(symbol1_prices['time']) & set(symbol2_prices['time']))
        len_smallest_set = int(min([len(symbol1_prices.index), len(symbol2_prices.index)]))
        len_largest_set = int(max([len(symbol1_prices.index), len(symbol2_prices.index)]))
        similar_size = len_largest_set * .9 <= len_smallest_set
        enough_overlap = len(intersect_dates) >= len_smallest_set * .9
        suitable = similar_size and enough_overlap

        if suitable:
            # Calculate coefficient on close prices

            # First filter prices to only include those that intersect
            symbol1_prices_filtered = symbol1_prices[symbol1_prices['time'].isin(intersect_dates)]
            symbol2_prices_filtered = symbol2_prices[symbol2_prices['time'].isin(intersect_dates)]

            # Calculate coefficient. Only use if p value is < 0.01 (highly likely that coefficient is valid and null
            # hypothesis is false).
            coefficient_with_p_value = pearsonr(symbol1_prices_filtered['close'], symbol2_prices_filtered['close'])
            coefficient = None if coefficient_with_p_value[1] > 0.01 else coefficient_with_p_value[0]

            # If NaN, change to None
            if coefficient is not None and math.isnan(coefficient):
                coefficient = None

        return coefficient



