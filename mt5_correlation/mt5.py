import pandas as pd
import MetaTrader5 as mt5
import logging


class MT5:
    """
    A class to connect to and interface with MetaTrader 5
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



