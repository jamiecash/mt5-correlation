import math
import logging
import pandas as pd
from datetime import datetime, timedelta
import time
import sched
import threading
import pytz
from scipy.stats.stats import pearsonr
import pickle
import inspect
import sys
import numpy as np

from mt5_correlation.mt5 import MT5


class Correlation:
    """
    A class to maintain the state of the calculated correlation coefficients.
    """

    # Connection to MetaTrader5
    __mt5 = None

    # Minimum base coefficient for monitoring. Symbol pairs with a lower correlation
    # coefficient than ths won't be monitored.
    monitoring_threshold = 0.9

    # Toggle on whether we are monitoring or not. Set through start_monitor and stop_monitor
    __monitoring = False

    # Monitoring calculation params, interval, cache_time, autosave and filename. Passed to start_monitor
    __monitoring_params = []
    __interval = None
    __cache_time = None
    __autosave = None
    __filename = None

    # First run of scheduler
    __first_run = True

    # The price data used to calculate the correlations
    __price_data = None

    # The shortest timeframe (which is the largest value) for calculate_from. This will be used when we update
    # the coefficient_data dataframe. All calculations for all values specified in calculate_from will be stored in
    # coefficient_history, however only the shortest timeframe will be updated in coefficient_data.
    __shortest_timeframe = None

    # Coefficient data and history. Will be created in init call to __reset_coefficient_data
    coefficient_data = None
    coefficient_history = None

    # Stores tick data used to calculate coefficient during Monitor.
    # Dict: {Symbol: [retrieved datetime, ticks dataframe]}
    __monitor_tick_data = {}

    def __init__(self):
        # Logger
        self.__log = logging.getLogger(__name__)

        # Connection to MetaTrader5
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

    def load(self, filename):
        """
        Loads calculated coefficients, price data used to calculate them and tick data used during monitoring.
        coefficients
        :param filename: The filename for the coefficient data to load.
        :return:
        """
        # Load data
        with open(filename, 'rb') as file:
            loaded_dict = pickle.load(file)

        # Get data from loaded dict and save
        self.coefficient_data = loaded_dict["coefficient_data"]
        self.__price_data = loaded_dict["price_data"]
        self.__monitor_tick_data = loaded_dict["monitor_tick_data"]
        self.coefficient_history = loaded_dict["coefficient_history"]

    def save(self, filename):
        """
        Saves the calculated coefficients, the price data used to calculate and the tick data for monitoring to a file.
        :param filename: The filename to save the data to.
        :return:
        """
        # Add data to dict then use pickle to save
        save_dict = {"coefficient_data": self.coefficient_data, "price_data": self.__price_data,
                     "monitor_tick_data": self.__monitor_tick_data, "coefficient_history": self.coefficient_history}
        with open(filename, 'wb') as file:
            pickle.dump(save_dict, file, protocol=pickle.HIGHEST_PROTOCOL)

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
        :param overlap_pct:The dates and times in the two sets of data must match. The coefficient will only be
            calculated against the dates that overlap. Any non overlapping dates will be discarded. This setting
            specifies the minimum size of the overlapping data when compared to the smallest set as a %. A coefficient
            will not be calculated if this threshold is not met.
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
            self.start_monitor(interval=self.__interval, calculation_params=self.__monitoring_params,
                               cache_time=self.__cache_time, autosave=self.__autosave, filename=self.__filename)

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

    def start_monitor(self, interval, calculation_params, cache_time=10, autosave=False, filename='autosave.cpd'):
        """
        Starts monitor to continuously update the coefficient for all symbol pairs in that meet the min_coefficient
        threshold.

        :param interval: How often to check in seconds
        :param calculation_params: A single dict or list of dicts containing the parameters for the coefficient
            calculations. On every iteration, a coefficient will be calculated for every set of params in list. Params
            contain the following values:
                from: The number of minutes of tick data to use for calculation. This can be a single value or
                    a list. If a list, then calculations will be performed for every from date in list.
                min_prices: The minimum number of prices that should be used to calculate coefficient. If this threshold
                    is not met then returned coefficient will be None
                max_set_size_diff_pct: Correlations will only be calculated if the sizes of the two price data sets are
                    within this pct of each other
                overlap_pct: The dates and times in the two sets of data must match. The coefficient will only be
                    calculated against the dates that overlap. Any non overlapping dates will be discarded. This
                    setting specifies the minimum size of the overlapping data when compared to the smallest set as a %.
                    A coefficient will not be calculated if this threshold is not met.
                max_p_value: The maximum p value for the correlation to be meaningful
        :param cache_time: Tick data is cached so that we can check coefficients for multiple symbol pairs and reuse
            the tick data. Number of seconds to cache tick data for before it becomes stale.
        :param autosave: Whether to autosave after every monitor run. If there is no filename specified then will
            create one named autosave.cpd
        :param filename: Filename for autosave. Default is autosave.cpd.

        :return: correlation coefficient, or None if coefficient could not be calculated.
        """

        if self.__monitoring:
            self.__log.debug(f"Request to start monitor when monitor is already running. Monitor will be stopped and"
                             f"restarted with new parameters.")
            self.stop_monitor()

        self.__log.debug(f"Starting monitor.")
        self.__monitoring = True

        # Store the calculation params. If it isn't a list, convert to list of one to make code simpler later on.
        self.__monitoring_params = calculation_params if isinstance(calculation_params, list) \
            else [calculation_params, ]

        # Store the other params. We will need these later if monitor is stopped and needs to be restarted. This
        # happens in calculate.
        self.__interval = interval
        self.__cache_time = cache_time
        self.__autosave = autosave
        self.__filename = filename

        # Store the shortest timeframe (which is the largest value) for calculate_from. This will be used when we update
        # the coefficient_data dataframe. All calculations for all values specified in calculate_from will be stored in
        # coefficient_history, however only the shortest timeframe will be updated in coefficient_data.
        for params in self.__monitoring_params:
            if self.__shortest_timeframe is None:
                self.__shortest_timeframe = params['from']
            else:
                self.__shortest_timeframe = min(self.__shortest_timeframe, params['from'])

        # Create thread to run monitoring This will call private __monitor method that will run the calculation and
        # keep scheduling itself while self.monitoring is True.
        params = {'interval': interval, "cache_time": cache_time, 'autosave': autosave, 'filename': filename}
        thread = threading.Thread(target=self.__monitor, kwargs=params)
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

        :param symbol1_prices: Pandas dataframe containing prices for symbol 1
        :param symbol2_prices: Pandas dataframe containing prices for symbol 2
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

    def get_coefficient_history(self, symbol1, symbol2, timeframe=None):
        """
        Returns the coefficient history for the specified symbol pair calculated during this instance.
        Coefficient history does not persist between instances.
        :param symbol1:
        :param symbol2:
        :param timeframe: Only return history for the specified timeframe. If None, this is ignored and all history
            records are returned for the specified symbols
        :return: dataframe containing history of coefficient data.
        """
        history = self.coefficient_history[(self.coefficient_history['Symbol 1'] == symbol1) &
                                           (self.coefficient_history['Symbol 2'] == symbol2)]

        # If calculate from was specified, filter on it.
        if timeframe is not None:
            history = history[(history['Timeframe'] == timeframe)]

        return history

    def clear_coefficient_history(self):
        """
        Clears the coefficient history for all symbol pairs
        :return:
        """
        # Create dataframes for coefficient history.
        coefficient_history_columns = ['Symbol 1', 'Symbol 2', 'Coefficient', 'Timeframe', 'Date From', 'Date To']
        self.coefficient_history = pd.DataFrame(columns=coefficient_history_columns)

        # Clear tick data
        self.__monitor_tick_data = {}

        # Clear columns from coefficient data
        self.coefficient_data['Last Check'] = np.NaN
        self.coefficient_data['Last Coefficient'] = np.NaN

    def get_ticks(self, symbol, date_from=None, date_to=None, cache_time=0, cache_only=False):
        """
        Returns the ticks for the specified symbol. Get's from cache if available and not older than cache_timeframe.

        :param symbol: Name of symbol to get ticks for.
        :param date_from: Date to get ticks from. Can only be None if getting from cache (cache_only=True)
        :param date_to:Date to get ticks to. Can only be None if getting from cache (cache_only=True)
        :param cache_time: Number of seconds before cached data is stale. If > than this number of seconds has elapsed,
            get data from source and refresh cache.
        :param cache_only: Only retrieve from cache. cache_time is ignored. Returns None if symbol is not available in
            cache.

        :return:
        """

        timezone = pytz.timezone("Etc/UTC")
        utc_now = datetime.now(tz=timezone)

        ticks = None

        # Cache only
        if cache_only:
            if symbol in self.__monitor_tick_data:
                ticks = self.__monitor_tick_data[symbol][1]
        # Check if we already have it and it is not stale
        elif symbol in self.__monitor_tick_data and utc_now < \
                self.__monitor_tick_data[symbol][0] + timedelta(seconds=cache_time):
            # Cached ticks are not stale. Get them
            ticks = self.__monitor_tick_data[symbol][1]
            self.__log.debug(f"Ticks for {symbol} retrieved from cache.")
        else:
            # Data does not exist in cache or cached data is stale. Retrieve from source and cache.
            ticks = self.__mt5.get_ticks(symbol=symbol, from_date=date_from, to_date=date_to)
            self.__monitor_tick_data[symbol] = [utc_now, ticks]
            self.__log.debug(f"Ticks for {symbol} retrieved from source and cached.")
        return ticks

    def __monitor(self, interval, cache_time=10, autosave=False, filename='autosave.cpd'):
        """
        The actual monitor method. Private. This should not be called outside of this class. Use start_monitoring and
        stop_monitoring.

        :param interval: How often to check in seconds
        :param cache_time: Tick data is cached so that we can check coefficients for multiple symbol pairs and reuse
            the tick data. Number of seconds to cache tick data for before it becomes stale.
        :param autosave: Whether to autosave after every monitor run. If there is no filename specified then will
            create one named autosave.cpd
        :param filename: Filename for autosave. Default is autosave.cpd.

        :return: correlation coefficient, or None if coefficient could not be calculated.
        """
        self.__log.debug(f"In monitor event. Monitoring: {self.__monitoring}.")

        # Only run if monitor is not stopped
        if self.__monitoring:
            # Update all coefficients
            self.__update_all_coefficients(cache_time=cache_time)

            # Autosave
            if autosave:
                self.save(filename=filename)

            # Schedule the timer to run again
            params = {'interval': interval, "cache_time": cache_time, 'autosave': autosave, 'filename': filename}
            self.__scheduler.enter(delay=interval, priority=1, action=self.__monitor, kwargs=params)

            # Log the stack. Debug stack overflow
            self.__log.debug(f"Current stack size: {len(inspect.stack())} Recursion limit: {sys.getrecursionlimit()}")

            # Run
            if self.__first_run:
                self.__first_run = False
                self.__scheduler.run()

    def __update_coefficients(self, symbol1, symbol2, cache_time=10):
        """
        Updates the long and short coefficients for the specified symbol pair
        :param symbol1: Name of symbol to calculate coefficient for.
        :param symbol2: Name of symbol to calculate coefficient for.
        :param cache_time: Tick data is cached so that we can check coefficients for multiple symbol pairs and reuse
            the tick data. Number of seconds to cache tick data for before it becomes stale.
        :return: correlation coefficient, or None if coefficient could not be calculated.
        """

        # Get the largest value of from in monitoring_params. This will be used to retrieve the data. We will only
        # retrieve once and use for every set of params by getting subset of the data.
        max_from = None
        for params in self.__monitoring_params:
            if max_from is None:
                max_from = params['from']
            else:
                max_from = max(max_from, params['from'])

        # Date range for data
        timezone = pytz.timezone("Etc/UTC")
        date_to = datetime.now(tz=timezone)
        date_from = date_to - timedelta(minutes=max_from)

        # Get the tick data for the longest timeframe calculation.
        symbol1ticks = self.get_ticks(symbol=symbol1, date_from=date_from, date_to=date_to, cache_time=cache_time)
        symbol2ticks = self.get_ticks(symbol=symbol2, date_from=date_from, date_to=date_to, cache_time=cache_time)

        # Resample to 1 sec OHLC, this will help with coefficient calculation ensuring that we dont have more than
        # one tick per second and ensuring that times can match. We will need to set the index to time for the
        # resample then revert back to a 'time' column. We will then need to remove rows with nan in 'close' price
        s1_prices = None
        s2_prices = None
        if symbol1ticks is not None and symbol2ticks is not None and len(symbol1ticks.index) > 0 and \
                len(symbol2ticks.index) > 0:

            try:
                symbol1ticks = symbol1ticks.set_index('time')
                symbol2ticks = symbol2ticks.set_index('time')
                s1_prices = symbol1ticks['ask'].resample('1S').ohlc()
                s2_prices = symbol2ticks['ask'].resample('1S').ohlc()
            except RecursionError:
                self.__log.warning(f"Coefficient could not be calculated for {symbol1}:{symbol2}. prices could not "
                                   f"be resampled.")
            else:
                s1_prices.reset_index(inplace=True)
                s2_prices.reset_index(inplace=True)
                s1_prices = s1_prices[s1_prices['close'].notna()]
                s2_prices = s2_prices[s2_prices['close'].notna()]

            # Calculate for all sets of monitoring_params
            if s1_prices is not None and s2_prices is not None:
                for params in self.__monitoring_params:
                    # Get the from date as a datetime64
                    date_from_subset = pd.Timestamp(date_to - timedelta(minutes=params['from'])).to_datetime64()

                    # Get subset of the price data
                    s1_prices_subset = s1_prices[(s1_prices['time'] >= date_from_subset)]
                    s2_prices_subset = s2_prices[(s2_prices['time'] >= date_from_subset)]

                    # Calculate the coefficient
                    coefficient = \
                        self.calculate_coefficient(symbol1_prices=s1_prices_subset, symbol2_prices=s2_prices_subset,
                                                   min_prices=params['min_prices'],
                                                   max_set_size_diff_pct=params['max_set_size_diff_pct'],
                                                   overlap_pct=params['overlap_pct'], max_p_value=params['max_p_value'])

                    self.__log.debug(f"Symbol pair {symbol1}:{symbol2} has a coefficient of {coefficient} for last "
                                     f"{params['from']} minutes.")

                    # Update the coefficient data
                    if coefficient is not None:
                        self.__update_coefficient_data(symbol1=symbol1, symbol2=symbol2, coefficient=coefficient,
                                                       timeframe=params['from'], date_from=date_from_subset,
                                                       date_to=date_to)

    def __update_all_coefficients(self, cache_time=10):
        """
        Updates the coefficient for all symbol pairs in that meet the min_coefficient threshold. Symbol pairs that meet
        the threshold can be accessed through the filtered_coefficient_data property.

        :param cache_time: Tick data is cached so that we can check coefficients for multiple symbol pairs and reuse
            the tick data. Number of seconds to cache tick data for before it becomes stale.
        """
        # Update  latest coefficient for every pair
        for index, row in self.filtered_coefficient_data.iterrows():
            symbol1 = row['Symbol 1']
            symbol2 = row['Symbol 2']
            self.__update_coefficients(symbol1=symbol1, symbol2=symbol2, cache_time=cache_time)

    def __reset_coefficient_data(self):
        """
        Clears coefficient data and history.
        :return:
        """
        # Create dataframes for coefficient data.
        coefficient_data_columns = ['Symbol 1', 'Symbol 2', 'Base Coefficient', 'UTC Date From', 'UTC Date To',
                                    'Timeframe', 'Last Check', 'Last Coefficient']
        self.coefficient_data = pd.DataFrame(columns=coefficient_data_columns)

        # Clear coefficient history
        self.clear_coefficient_history()

        # Clear price data
        self.__price_data = None

    def __update_coefficient_data(self, symbol1, symbol2, coefficient, timeframe, date_from, date_to):
        """
        Updates the coefficient data with the latest coefficient and adds to coefficient history.
        :param symbol1:
        :param symbol2:
        :param coefficient: The coefficient calculated
        :param timeframe: The number of minutes of price data used to calculate the coefficient
        :param date_from: The date from for which the coefficient was calculated
        :param date_to: The date from for which the coefficient was calculated
        :return:
        """

        timezone = pytz.timezone("Etc/UTC")
        now = datetime.now(tz=timezone)

        # Update data if we have a coefficient and add to history
        if coefficient is not None:
            # The coefficient data table is only updated for the shortest calculation timeframe.
            if timeframe == self.__shortest_timeframe:
                self.coefficient_data.loc[(self.coefficient_data['Symbol 1'] == symbol1) &
                                          (self.coefficient_data['Symbol 2'] == symbol2),
                                          'Last Check'] = now

                self.coefficient_data.loc[(self.coefficient_data['Symbol 1'] == symbol1) &
                                          (self.coefficient_data['Symbol 2'] == symbol2),
                                          'Last Coefficient'] = coefficient

            # However the history data is always updated
            row = pd.DataFrame(columns=self.coefficient_history.columns,
                               data=[[symbol1, symbol2, coefficient, timeframe, date_from, date_to]])
            self.coefficient_history = self.coefficient_history.append(row)
