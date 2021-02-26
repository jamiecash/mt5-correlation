import math
import logging
import pandas as pd
from datetime import datetime, timedelta
import time
import sched
import threading
import pytz
from scipy.stats.stats import pearsonr
import yaml
import pickle

from mt5_correlation.mt5 import MT5


class Correlation:
    """
    A class to maintain the state of the calculated correlation coefficients.
    """

    # Connection to metatrader
    __mt5 = None

    # Minimum base coefficient for monitoring. Symbol pairs with a lower correlation
    # coefficient than ths won't be monitored.
    monitoring_threshold = 0.9

    # Toggle on whether we are monitoring or not. Set through start_monitor and stop_monitor
    __monitoring = False
    __monitoring_params = {}

    # The price data used to calculate the correlations
    __price_data = None

    # Coefficient data and history. Will be created as dataframes in Init
    coefficient_data = None
    coefficient_history = None

    # Cache for ticks. Dict: {Symbol: [retrieved datetime, ticks dataframe]}
    __ticks = {}

    def __init__(self):
        # Logger
        self.__log = logging.getLogger(__name__)

        # Connection to metatrader
        self.__mt5 = MT5()

        # Create dataframe for coefficient data
        self.__reset_coefficient_data()

        # Create timer for continuous monitoring
        self.__scheduler = sched.scheduler(time.time, time.sleep)

    @property
    def filtered_coefficient_data(self):
        """
        :return: Coefficient data filtered so that all base coefficients >= monitoring_threshold
        """
        if self.coefficient_data is not None:
            return self.coefficient_data.loc[self.coefficient_data['Base Coefficient'] >= self.monitoring_threshold]
        else:
            return None

    def load(self, filename, price_data_filename=None):
        """
        Loads a csv file containing calculated coefficients, and optionally the price data used to calculate those
        coefficients
        :param filename: The filename for the coefficient data to load.
        :param price_data_filename: The filename for the price data to load.
        :return:
        """
        # Load coefficients file
        self.coefficient_data = pd.read_csv(filename)

        # If specified, load price data yaml file
        if price_data_filename is not None:
            self.__price_data = {}  # Clear
            with open(price_data_filename, 'rb') as file:
                self.__price_data = pickle.load(file)

    def save(self, filename, price_data_filename=None):
        """
        Saves the calculated coefficients as a csv file
        :param filename: The filename for the coefficient data to save to.
        :param price_data_filename: The filename for the price data to save to.
        :return:
        """
        # Save the coefficient data
        self.coefficient_data.to_csv(filename, index=False)

        # Save the price data if required
        if price_data_filename is not None:
            with open(price_data_filename, 'wb') as file:
                pickle.dump(self.__price_data, file, protocol=pickle.HIGHEST_PROTOCOL)

    def calculate(self, date_from, date_to, timeframe, min_prices=100, max_set_size_diff_pct=90, overlap_pct=90,
                  max_p_value=0.05):
        """
        Calculates correlation coefficient between all symbols in MetaTrader5 Market Watch. Updates coefficient data.

        :param date_from: From date for price data from which to calculate correlation coefficients
        :param date_to: To date for price data from which to calculate correlation coefficients
        :param timeframe: Timeframe for price data from which to calculate correlation coefficients
        :param min_prices: The minimum number of prices that should be used to calculate coefficient. If this threshold
            is not met then returned coefficient will be None
        :param max_set_size_diff_pct: Correlations will only be calculated if the sizes of the two price data sets are
            within this pct of each other
        :param overlap_pct:
        :param max_p_value: The maximum p value for the correlation to be meaningful

        :return:
        """

        coefficient = None

        # If we are monitoring, stop. We will need to restart later
        was_monitoring = self.__monitoring
        if self.__monitoring:
            self.stop_monitor()

        # Clear the existing correlations
        self.__reset_coefficient_data()

        # Get all visible symbols
        symbols = self.__mt5.get_symbols()

        # Get price data for selected symbols. 1 week of 15 min OHLC data for each symbol. Add to dict.
        self.__price_data = {}
        for symbol in symbols:
            self.__price_data[symbol] = self.__mt5.get_prices(symbol=symbol, from_date=date_from, to_date=date_to,
                                                              timeframe=timeframe)

        # Loop through all symbol pair combinations and calculate coefficient. Make sure you don't double count pairs
        # eg. (USD/GBP AUD/USD vs AUD/USD USD/GBP). Use grid of all symbols with i and j axis. j starts at i + 1 to
        # avoid duplicating. We will store all coefficients in a dataframe for export as CSV.
        index = 0
        # There will be (x^2 - x) / 2 pairs where x is number of symbols
        num_pair_combinations = int((len(symbols) ** 2 - len(symbols)) / 2)

        for i in range(0, len(symbols)):
            symbol1 = symbols[i]

            for j in range(i + 1, len(symbols)):
                symbol2 = symbols[j]
                index += 1

                # Get price data for both symbols
                symbol1_price_data = self.__price_data[symbol1]
                symbol2_price_data = self.__price_data[symbol2]

                # Get coefficient
                if symbol1_price_data is not None and symbol2_price_data is not None:
                    coefficient = self.calculate_coefficient(symbol1_prices=symbol1_price_data,
                                                             symbol2_prices=symbol2_price_data,
                                                             min_prices=min_prices,
                                                             max_set_size_diff_pct=max_set_size_diff_pct,
                                                             overlap_pct=overlap_pct, max_p_value=max_p_value)

                # Store if valid
                if coefficient is not None:

                    self.coefficient_data = \
                        self.coefficient_data.append({'Symbol 1': symbol1, 'Symbol 2': symbol2,
                                                      'Base Coefficient': coefficient, 'UTC Date From': date_from,
                                                      'UTC Date To': date_to, 'Timeframe': timeframe},
                                                     ignore_index=True)
                    self.__log.debug(f"Pair {index} of {num_pair_combinations}: {symbol1}:{symbol2} has a "
                                     f"coefficient of {coefficient}.")
                else:
                    self.__log.debug(f"Coefficient for pair {index} of {num_pair_combinations}: {symbol1}:"
                                     f"{symbol2} could no be calculated.")

        # Sort, highest correlated first
        self.coefficient_data = self.coefficient_data.sort_values('Base Coefficient', ascending=False)

        # If we were monitoring, we stopped, so start again.
        if was_monitoring:
            self.start_monitor(interval=self.__monitoring_params['interval'],
                               from_mins=self.__monitoring_params['from_mins'],
                               min_prices=self.__monitoring_params['min_prices'],
                               max_set_size_diff_pct=self.__monitoring_params['max_set_size_diff_pct'],
                               overlap_pct=self.__monitoring_params['overlap_pct'],
                               max_p_value=self.__monitoring_params['max_p_value'])

    def get_price_data(self, symbol):
        """
        Returns the price data used to calculate the base coefficients for the specified symbol
        :param symbol: Symbol to get price data for.
        :return: price data
        """
        price_data = None
        if symbol in self.__price_data:
            price_data = self.__price_data[symbol]

        return price_data

    def start_monitor(self, interval, from_mins, min_prices=100, max_set_size_diff_pct=90, overlap_pct=90,
                      max_p_value=0.05, cache_time=10):
        """
        Starts monitor to continuously update the coefficient for all symbol pairs in that meet the min_coefficient
        threshold.

        :param interval: How often to check in seconds
        :param from_mins: The number of minutes of tick data to use for calculations
        :param min_prices: The minimum number of prices that should be used to calculate coefficient. If this threshold
            is not met then returned coefficient will be None
        :param max_set_size_diff_pct: Correlations will only be calculated if the sizes of the two price data sets are
            within this pct of each other
        :param overlap_pct:
        :param max_p_value: The maximum p value for the correlation to be meaningful
        :param cache_time: Tick data is cached so that we can check coefficients for multiple symbol pairs and reuse
            the tick data. Number of seconds to cache tick data for before it becomes stale.

        :return: correlation coefficient, or None if coefficient could not be calculated.
        """

        if self.__monitoring:
            self.__log.debug(f"Request to start monitor when monitor is already running. Monitor will be stopped and"
                             f"restarted with new parameters.")
            self.stop_monitor()

        self.__log.debug(f"Starting monitor.")
        self.__monitoring = True

        # Create thread to run monitoring This will call private __monitor method that will run the calculation and
        # keep scheduling itself while self.monitoring is True. Store the params. We will need to use these if we have
        # to stop and restart the monitor. Note, this happens during calculate
        self.__monitoring_params = {'interval': interval, 'from_mins': from_mins,
                                    'min_prices': min_prices, 'max_set_size_diff_pct': max_set_size_diff_pct,
                                    'overlap_pct': overlap_pct, 'max_p_value': max_p_value, 'cache_time': cache_time}
        thread = threading.Thread(target=self.__monitor, kwargs=self.__monitoring_params)
        thread.start()

    def stop_monitor(self):
        """
        Stops monitoring symbol pairs for correlation.
        :return:
        """
        if self.__monitoring:
            self.__log.debug(f"Stopping monitor.")
            self.__monitoring = False
        else:
            self.__log.debug(f"Request to stop monitor when it is not running. No action taken.")

    def calculate_coefficient(self, symbol1_prices, symbol2_prices, min_prices: int = 100,
                              max_set_size_diff_pct: int = 90, overlap_pct: int = 90,
                              max_p_value: float = 0.05):
        """
        Calculates the correlation coefficient between two sets of price data. Uses close price.

        :param symbol1_prices: Pandas dataframe containing prices or ticks for symbol 1
        :param symbol2_prices: Pandas dataframe containing prices or ticks for symbol 2
        :param min_prices: The minimum number of prices that should be used to calculate coefficient. If this threshold
            is not met then returned coefficient will be None
        :param max_set_size_diff_pct: Correlations will only be calculated if the sizes of the two price data sets are
            within this pct of each other
        :param overlap_pct:
        :param max_p_value: The maximum p value for the correlation to be meaningful

        :return: correlation coefficient, or None if coefficient could not be calculated.
        :rtype: float or None
        """

        assert symbol1_prices is not None and symbol2_prices is not None

        # Calculate size of intersection and determine if prices for symbols have enough overlapping timestamps for
        # correlation coefficient calculation to be meaningful. Is the smallest set at least max_set_size_diff_pct % of
        # the size of the largest set and is the overlap set size at least overlap_pct % the size of the smallest set?
        coefficient = None

        intersect_dates = (set(symbol1_prices['time']) & set(symbol2_prices['time']))
        len_smallest_set = int(min([len(symbol1_prices.index), len(symbol2_prices.index)]))
        len_largest_set = int(max([len(symbol1_prices.index), len(symbol2_prices.index)]))
        similar_size = len_largest_set * (max_set_size_diff_pct / 100) <= len_smallest_set
        enough_overlap = len(intersect_dates) >= len_smallest_set * (overlap_pct / 100)
        enough_prices = len_smallest_set >= min_prices
        suitable = similar_size and enough_overlap and enough_prices

        if suitable:
            # Calculate coefficient on close prices

            # First filter prices to only include those that intersect
            symbol1_prices_filtered = symbol1_prices[symbol1_prices['time'].isin(intersect_dates)]
            symbol2_prices_filtered = symbol2_prices[symbol2_prices['time'].isin(intersect_dates)]

            # Calculate coefficient. Only use if p value is < 0.01 (highly likely that coefficient is valid and null
            # hypothesis is false).
            coefficient_with_p_value = pearsonr(symbol1_prices_filtered['close'], symbol2_prices_filtered['close'])
            coefficient = None if coefficient_with_p_value[1] > max_p_value else coefficient_with_p_value[0]

            # If NaN, change to None
            if coefficient is not None and math.isnan(coefficient):
                coefficient = None

        self.__log.debug(f"Calculate coefficient returning {coefficient}. "
                         f"Symbol 1 Prices: {len(symbol1_prices)}  Symbol 2 Prices: {len(symbol2_prices)} "
                         f"Overlap Prices: {len(intersect_dates)} Similar size: {similar_size} "
                         f"Enough overlap: {enough_overlap} Enough prices: {enough_prices} Suitable: {suitable}.")

        return coefficient

    def get_coefficient_history(self, symbol1, symbol2):
        """
        Returns the coefficient history for the specified symbol pair calculated during this instance.
        Coefficient history does not persist between instances.
        :param symbol1:
        :param symbol2:
        :return: dataframe containing history of coefficient data.
        """
        history = self.coefficient_history[(self.coefficient_history['Symbol 1'] == symbol1) &
                                           (self.coefficient_history['Symbol 2'] == symbol2)]
        return history

    def __monitor(self, interval, from_mins, min_prices=100, max_set_size_diff_pct=90, overlap_pct=90,
                  max_p_value=0.05, cache_time=10):
        """
        The actual monitor method. Private. This should not be called outside of this class. Use start_monitoring and
        stop_monitoring.

        :param interval: How often to check in seconds
        :param from_mins: The number of minutes of tick data to use for calculations
        :param min_prices: The minimum number of prices that should be used to calculate coefficient. If this threshold
            is not met then returned coefficient will be None
        :param max_set_size_diff_pct: Correlations will only be calculated if the sizes of the two price data sets are
            within this pct of each other
        :param overlap_pct:
        :param max_p_value: The maximum p value for the correlation to be meaningful
        :param cache_time: Tick data is cached so that we can check coefficients for multiple symbol pairs and reuse
            the tick data. Number of seconds to cache tick data for before it becomes stale.

        :return: correlation coefficient, or None if coefficient could not be calculated.
        """
        self.__log.debug(f"In monitor event. Monitoring: {self.__monitoring}.")

        # Only run if monitor is not stopped
        if self.__monitoring:
            # Update all coefficients
            self.__update_all_coefficients(from_mins=from_mins, min_prices=min_prices,
                                           max_set_size_diff_pct=max_set_size_diff_pct, overlap_pct=overlap_pct,
                                           max_p_value=max_p_value, cache_time=cache_time)

            # Schedule the timer to run again
            params = {'interval': interval, 'from_mins': from_mins, 'min_prices': min_prices,
                      'max_set_size_diff_pct': max_set_size_diff_pct, 'overlap_pct': overlap_pct,
                      'max_p_value': max_p_value, "cache_time": cache_time}
            self.__scheduler.enter(delay=interval, priority=1, action=self.__monitor, kwargs=params)
            self.__scheduler.run()

    def __update_coefficient(self, symbol1, symbol2, from_mins, min_prices=100, max_set_size_diff_pct=90,
                             overlap_pct=90, max_p_value=0.05, cache_time=10):
        """
        Updates the coefficient for the specified symbol pair
        :param symbol1: Name of symbol to calculate coefficient for.
        :param symbol2: Name of symbol to calculate coefficient for.
        :param from_mins: The number of minutes of tick data to use for calculations
        :param min_prices: The minimum number of prices that should be used to calculate coefficient. If this threshold
            is not met then returned coefficient will be None
        :param max_set_size_diff_pct: Correlations will only be calculated if the sizes of the two price data sets are
            within this pct of each other
        :param overlap_pct:
        :param max_p_value: The maximum p value for the correlation to be meaningful
        :param cache_time: Tick data is cached so that we can check coefficients for multiple symbol pairs and reuse
            the tick data. Number of seconds to cache tick data for before it becomes stale.
        :return: correlation coefficient, or None if coefficient could not be calculated.
        """

        coefficient = None

        # Get dates
        # From and to dates for calculations.
        timezone = pytz.timezone("Etc/UTC")
        date_to = datetime.now(tz=timezone)
        date_from = date_to - timedelta(minutes=from_mins)

        # Get the tick data
        symbol1ticks = self.__get_ticks(symbol=symbol1, date_from=date_from, date_to=date_to, cache_time=cache_time)
        symbol2ticks = self.__get_ticks(symbol=symbol2, date_from=date_from, date_to=date_to, cache_time=cache_time)

        # Resample to 1 sec OHLC, this will help with coefficient calculation ensuring that we dont have more than one
        # tick per second and ensuring that times can match. We will need to set the index to time for the resample
        # then revert back to a 'time' column. We will then need to remove rows with nan in 'close' price
        if symbol1ticks is not None and symbol2ticks is not None and \
                len(symbol1ticks.index) > 0 and len(symbol2ticks.index) > 0:
            symbol1ticks = symbol1ticks.set_index('time')
            symbol2ticks = symbol2ticks.set_index('time')
            try:
                symbol1prices = symbol1ticks['ask'].resample('1S').ohlc()
                symbol2prices = symbol2ticks['ask'].resample('1S').ohlc()
            except RecursionError:
                self.__log.warning(f"Coefficient could not be calculated for {symbol1}:{symbol2} as prices could not "
                                   f"be resampled.")
            else:
                symbol1prices.reset_index(inplace=True)
                symbol2prices.reset_index(inplace=True)
                symbol1prices = symbol1prices[symbol1prices['close'].notna()]
                symbol2prices = symbol2prices[symbol2prices['close'].notna()]

                # Calculate the coefficient
                coefficient = self.calculate_coefficient(symbol1_prices=symbol1prices, symbol2_prices=symbol2prices,
                                                         min_prices=min_prices,
                                                         max_set_size_diff_pct=max_set_size_diff_pct,
                                                         overlap_pct=overlap_pct, max_p_value=max_p_value)

                self.__log.debug(f"Symbol pair {symbol1}:{symbol2} has a coefficient of {coefficient}.")
        else:
            coefficient = None

        # Update the coefficient data
        if coefficient is not None:
            self.__update_coefficient_data(symbol1=symbol1, symbol2=symbol2, coefficient=coefficient,
                                           date_from=date_from, date_to=date_to)

        return coefficient

    def __update_all_coefficients(self, from_mins, min_prices=100, max_set_size_diff_pct=90, overlap_pct=90,
                                  max_p_value=0.05, cache_time=10):
        """
        Updates the coefficient for all symbol pairs in that meet the min_coefficient threshold. Symbol pairs that meet
        the threshold can be accessed through the filtered_coefficient_data property.

        :param from_mins: The number of minutes of tick data to use for calculations
        :param min_prices: The minimum number of prices that should be used to calculate coefficient. If this threshold
            is not met then returned coefficient will be None
        :param max_set_size_diff_pct: Correlations will only be calculated if the sizes of the two price data sets are
            within this pct of each other
        :param overlap_pct:
        :param max_p_value: The maximum p value for the correlation to be meaningful
        :param cache_time: Tick data is cached so that we can check coefficients for multiple symbol pairs and reuse
            the tick data. Number of seconds to cache tick data for before it becomes stale.

        :return: correlation coefficient, or None if coefficient could not be calculated.
        """
        # Update  latest coefficient for every pair
        for index, row in self.filtered_coefficient_data.iterrows():
            symbol1 = row['Symbol 1']
            symbol2 = row['Symbol 2']
            self.__update_coefficient(symbol1=symbol1, symbol2=symbol2, from_mins=from_mins,
                                      min_prices=min_prices, max_set_size_diff_pct=max_set_size_diff_pct,
                                      overlap_pct=overlap_pct, max_p_value=max_p_value, cache_time=cache_time)

    def __get_ticks(self, symbol, date_from, date_to, cache_time):
        """
        Returns the ticks for the specified symbol. Get's from cache if available and not older than cache_timeframe.

        :param symbol: Name of symbol to get ticks for.
        :param date_from:
        :param date_to:
        :param cache_time: Number of seconds before cached data is stale. If > than this number of seconds has elapsed,
            get data from source and refresh cache.

        :return:
        """

        timezone = pytz.timezone("Etc/UTC")
        utc_now = datetime.now(tz=timezone)

        # Check if in cache and not stale
        if symbol in self.__ticks and utc_now < self.__ticks[symbol][0] + timedelta(seconds=cache_time):
            # Cached ticks are not stale. Get them
            ticks = self.__ticks[symbol][1]
            self.__log.debug(f"Ticks for {symbol} retrieved from cache.")
        else:
            # Data does not exist in cache or cached data is stale. Retrieve from source and cache.
            ticks = self.__mt5.get_ticks(symbol=symbol, from_date=date_from, to_date=date_to)
            self.__ticks[symbol] = [utc_now, ticks]
            self.__log.debug(f"Ticks for {symbol} retrieved from source and cached.")
        return ticks

    def __reset_coefficient_data(self):
        """
        Clears coefficient data and history.
        :return:
        """
        # Create dataframe for coefficient data
        coefficient_data_columns = ['Symbol 1', 'Symbol 2', 'Base Coefficient', 'UTC Date From', 'UTC Date To',
                                    'Timeframe', 'Last Check', 'Last Coefficient']
        self.coefficient_data = pd.DataFrame(columns=coefficient_data_columns)

        # Create dataframe for coefficient history
        coefficient_history_columns = ['Symbol 1', 'Symbol 2', 'Coefficient', 'UTC Date From', 'UTC Date To']
        self.coefficient_history = pd.DataFrame(columns=coefficient_history_columns)

    def __update_coefficient_data(self, symbol1, symbol2, coefficient, date_from, date_to):
        """
        Updates the coefficient data with the latest coefficient and adds to coefficient history.
        :param symbol1:
        :param symbol2:
        :param coefficient:
        :param date_from:
        :param date_to:
        :return:
        """

        timezone = pytz.timezone("Etc/UTC")
        now = datetime.now(tz=timezone)

        # Update data if we have a coefficient and add to history
        if coefficient is not None:
            self.coefficient_data.loc[(self.coefficient_data['Symbol 1'] == symbol1) &
                                      (self.coefficient_data['Symbol 2'] == symbol2),
                                      'Last Check'] = now

            self.coefficient_data.loc[(self.coefficient_data['Symbol 1'] == symbol1) &
                                      (self.coefficient_data['Symbol 2'] == symbol2),
                                      'Last Coefficient'] = coefficient

            row = pd.DataFrame(columns=self.coefficient_history.columns,
                               data=[[symbol1, symbol2, coefficient, date_from, date_to]])
            self.coefficient_history = self.coefficient_history.append(row)
