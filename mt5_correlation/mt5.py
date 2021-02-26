import pandas as pd
import MetaTrader5
import logging

# Timeframes
TIMEFRAME_M1 = MetaTrader5.TIMEFRAME_M1
TIMEFRAME_M2 = MetaTrader5.TIMEFRAME_M2
TIMEFRAME_M3 = MetaTrader5.TIMEFRAME_M3
TIMEFRAME_M4 = MetaTrader5.TIMEFRAME_M4
TIMEFRAME_M5 = MetaTrader5.TIMEFRAME_M5
TIMEFRAME_M6 = MetaTrader5.TIMEFRAME_M6
TIMEFRAME_M10 = MetaTrader5.TIMEFRAME_M10
TIMEFRAME_M12 = MetaTrader5.TIMEFRAME_M10
TIMEFRAME_M15 = MetaTrader5.TIMEFRAME_M15
TIMEFRAME_M20 = MetaTrader5.TIMEFRAME_M20
TIMEFRAME_M30 = MetaTrader5.TIMEFRAME_M30
TIMEFRAME_H1 = MetaTrader5.TIMEFRAME_H1
TIMEFRAME_H2 = MetaTrader5.TIMEFRAME_H2
TIMEFRAME_H3 = MetaTrader5.TIMEFRAME_H3
TIMEFRAME_H4 = MetaTrader5.TIMEFRAME_H4
TIMEFRAME_H6 = MetaTrader5.TIMEFRAME_H6
TIMEFRAME_H8 = MetaTrader5.TIMEFRAME_H8
TIMEFRAME_H12 = MetaTrader5.TIMEFRAME_H12
TIMEFRAME_D1 = MetaTrader5.TIMEFRAME_D1
TIMEFRAME_W1 = MetaTrader5.TIMEFRAME_W1
TIMEFRAME_MN1 = MetaTrader5.TIMEFRAME_MN1


class MT5:
    """
    A class to connect to and interface with MetaTrader 5
    """

    def __init__(self):
        # Connect to MetaTrader5. Opens if not already open.

        # Logger
        self.__log = logging.getLogger(__name__)

        # Open MT5 and log error if it could not open
        if not MetaTrader5.initialize():
            self.__log.error("initialize() failed")
            MetaTrader5.shutdown()

        # Print connection status
        self.__log.debug(MetaTrader5.terminal_info())

        # Print data on MetaTrader 5 version
        self.__log.debug(MetaTrader5.version())

    def __del__(self):
        # shut down connection to the MetaTrader 5 terminal
        MetaTrader5.shutdown()

    def get_symbols(self):
        """
        Gets list of symbols open in MT5 market watch.
        :return: list of symbol names
        """
        # Iterate symbols and get those in market watch.
        symbols = MetaTrader5.symbols_get()
        selected_symbols = []
        for symbol in symbols:
            if symbol.visible:
                selected_symbols.append(symbol.name)

        # Log symbol counts
        total_symbols = MetaTrader5.symbols_total()
        num_selected_symbols = len(selected_symbols)
        self.__log.debug(f"{num_selected_symbols} of {total_symbols} available symbols in Market Watch.")

        return selected_symbols

    def get_prices(self, symbol, from_date, to_date, timeframe):
        """
        Gets OHLC price data for the specified symbol.
        :param symbol: The name of the symbol to get the price data for.
        :param from_date: Date from when to retrieve data
        :param to_date: Date where to receive data to
        :param timeframe: The timeframe for the candes. Possible values are:
            TIMEFRAME_M1: 1 minute
            TIMEFRAME_M2: 2 minutes
            TIMEFRAME_M3: 3 minutes
            TIMEFRAME_M4: 4 minutes
            TIMEFRAME_M5: 5 minutes
            TIMEFRAME_M6: 6 minutes
            TIMEFRAME_M10: 10 minutes
            TIMEFRAME_M12: 12 minutes
            TIMEFRAME_M15: 15 minutes
            TIMEFRAME_M20: 20 minutes
            TIMEFRAME_M30: 30 minutes
            TIMEFRAME_H1: 1 hour
            TIMEFRAME_H2: 2 hours
            TIMEFRAME_H3: 3 hours
            TIMEFRAME_H4: 4 hours
            TIMEFRAME_H6: 6 hours
            TIMEFRAME_H8: 8 hours
            TIMEFRAME_H12: 12 hours
            TIMEFRAME_D1: 1 day
            TIMEFRAME_W1: 1 week
            TIMEFRAME_MN1: 1 month
        :return: Price data for symbol as dataframe
        """

        prices_dataframe = None

        # Get prices from MT5
        prices = MetaTrader5.copy_rates_range(symbol, timeframe, from_date, to_date)
        if prices is not None:
            self.__log.debug(f"{len(prices)} prices retrieved for {symbol}.")

            # Create dataframe from data and convert time in seconds to datetime format
            prices_dataframe = pd.DataFrame(prices)
            prices_dataframe['time'] = pd.to_datetime(prices_dataframe['time'], unit='s')

        return prices_dataframe

    def get_ticks(self, symbol, from_date, to_date):
        """
        Gets OHLC price data for the specified symbol.
        :param symbol: The name of the symbol to get the price data for.
        :param from_date: Date from when to retrieve data
        :param to_date: Date where to receive data to
        :return: Tick data for symbol as dataframe
        """

        ticks_dataframe = None

        # Get ticks from MT5
        ticks = MetaTrader5.copy_ticks_range(symbol, from_date, to_date, MetaTrader5.COPY_TICKS_ALL)

        # If ticks is None, there was an error
        if ticks is None:
            error = MetaTrader5.last_error()
            self.__log.error(f"Error retrieving ticks for {symbol}: {error}")
        else:
            self.__log.debug(f"{len(ticks)} ticks retrieved for {symbol}.")

            # Create dataframe from data and convert time in seconds to datetime format
            try:
                ticks_dataframe = pd.DataFrame(ticks)
                ticks_dataframe['time'] = pd.to_datetime(ticks_dataframe['time'], unit='s')
            except RecursionError:
                self.__log.warning("Error converting ticks to dataframe.")

        return ticks_dataframe
