import unittest
from unittest.mock import patch
import time
import mt5_correlation.correlation as correlation
import pandas as pd
from datetime import datetime, timedelta
from test_mt5 import Symbol
import random
import os


class TestCorrelation(unittest.TestCase):
    # Mock symbols. 4 Symbols, 3 visible.
    mock_symbols = [Symbol(name='SYMBOL1', visible=True),
                    Symbol(name='SYMBOL2', visible=True),
                    Symbol(name='SYMBOL3', visible=False),
                    Symbol(name='SYMBOL4', visible=True)]

    # Start and end date for price data and mock prices: base; correlated; and uncorrelated.
    start_date = None
    end_date = None
    price_columns = None
    mock_base_prices = None
    mock_correlated_prices = None
    mock_uncorrelated_prices = None

    def setUp(self):
        """
        Creates some price data fro use in tests
        :return:
        """
        # Start and end date for price data and mock price dataframes. One for: base; correlated; uncorrelated and
        # different dates.
        self.start_date = datetime(2021, 1, 1, 1, 5, 0)
        self.end_date = datetime(2021, 1, 1, 11, 30, 0)
        self.price_columns = ['time', 'close']
        self.mock_base_prices = pd.DataFrame(columns=self.price_columns)
        self.mock_correlated_prices = pd.DataFrame(columns=self.price_columns)
        self.mock_uncorrelated_prices = pd.DataFrame(columns=self.price_columns)
        self.mock_correlated_different_dates = pd.DataFrame(columns=self.price_columns)

        # Build the price data for the test. One price every 5 minutes for 500 rows. Base will use min for price,
        # correlated will use min + 5 and uncorrelated will use random
        for date in (self.start_date + timedelta(minutes=m) for m in range(0, 500*5, 5)):
            self.mock_base_prices = self.mock_base_prices.append(pd.DataFrame(columns=self.price_columns,
                                                                              data=[[date, date.minute]]))
            self.mock_correlated_prices = \
                self.mock_correlated_prices.append(pd.DataFrame(columns=self.price_columns,
                                                                data=[[date, date.minute + 5]]))
            self.mock_uncorrelated_prices = \
                self.mock_uncorrelated_prices.append(pd.DataFrame(columns=self.price_columns,
                                                                  data=[[date, random.randint(0, 1000000)]]))

            self.mock_correlated_different_dates = \
                self.mock_correlated_different_dates.append(pd.DataFrame(columns=self.price_columns,
                                                                         data=[[date + timedelta(minutes=100),
                                                                                date.minute + 5]]))

    @patch('mt5_correlation.mt5.MetaTrader5')
    def test_calculate(self, mock):
        """
        Test the calculate method. Uses mock for MT5 symbols and prices.
        :param mock:
        :return:
        """
        # Mock symbol return values
        mock.symbols_get.return_value = self.mock_symbols

        # Correlation class
        cor = correlation.Correlation()

        # Calculate for price data. We should have 100% matching dates in sets. Get prices should be called 3 times.
        # We dont have a SYMBOL2 as this is set as not visible. Correlations should be as follows:
        #   SYMBOL1:SYMBOL2 should be fully correlated (1)
        #   SYMBOL1:SYMBOL4 should be uncorrelated (0)
        #   SYMBOL2:SYMBOL4 should be uncorrelated (0)
        # We will not use p_value as the last set uses random numbers so p value will not be useful.
        mock.copy_rates_range.side_effect = [self.mock_base_prices, self.mock_correlated_prices,
                                             self.mock_uncorrelated_prices]
        cor.calculate(date_from=self.start_date, date_to=self.end_date, timeframe=5, min_prices=100,
                      max_set_size_diff_pct=100, overlap_pct=100, max_p_value=1)

        # Test the output. We should have 3 rows. S1:S2 c=1, S1:S4 c<1, S2:S4 c<1>
        self.assertEqual(len(cor.coefficient_data.index), 3, "There should be three correlations rows calculated.")
        self.assertEqual(cor.coefficient_data.iloc[0, 2], 1, "The correlation for SYMBOL1:SYMBOL2 should be 1.")
        self.assertTrue(cor.coefficient_data.iloc[1, 2] < 1, "The correlation for SYMBOL1:SYMBOL4 should be <1.")
        self.assertTrue(cor.coefficient_data.iloc[2, 2] < 1, "The correlation for SYMBOL2:SYMBOL4 should be <1.")

        # Set the monitoring threshold to 1 and get filtered correlations. There should only be 1
        cor.monitoring_threshold = 1
        self.assertEqual(len(cor.filtered_coefficient_data.index), 1, "There should only be 1 row in filtered "
                                                                      "coefficient data.")

        # Now were going to recalculate, but this time:
        #   SYMBOL1:SYMBOL2 will have non overlapping dates and coefficient should be None. There shouldn't be a row
        #   SYMBOL1:SYMBOL4 will be correlated
        #   SYMBOL2:SYMBOL4 will have non overlapping dates and coefficient should be None.  There shouldn't be a row.
        mock.copy_rates_range.side_effect = [self.mock_base_prices, self.mock_correlated_different_dates,
                                             self.mock_correlated_prices]
        cor.calculate(date_from=self.start_date, date_to=self.end_date, timeframe=5, min_prices=100,
                      max_set_size_diff_pct=100, overlap_pct=100, max_p_value=1)
        self.assertEqual(len(cor.coefficient_data.index), 1, "There should be one correlations rows calculated.")
        self.assertEqual(cor.coefficient_data.iloc[0, 2], 1, "The correlation for SYMBOL1:SYMBOL4 should be 1.")

        # Get the price data used to calculate the coefficients fro symbol 1. It should match mock_base_prices.
        price_data = cor.get_price_data('SYMBOL1')
        self.assertTrue(price_data.equals(self.mock_base_prices), "Price data returned post calculation should match "
                                                                  "mock price data.")

    def test_calculate_coefficient(self):
        """
        Tests the coefficient calculation.
        :return:
        """
        # Correlation class
        cor = correlation.Correlation()

        # Test 2 correlated sets
        coefficient = cor.calculate_coefficient(self.mock_base_prices, self.mock_correlated_prices)
        self.assertEqual(coefficient, 1, "Coefficient should be 1.")

        # Test 2 uncorrelated sets. Set p value to 1 to force correlation to be returned.
        coefficient = cor.calculate_coefficient(self.mock_base_prices, self.mock_uncorrelated_prices, max_p_value=1)
        self.assertTrue(coefficient < 1, "Coefficient should be < 1.")

        # Test 2 sets where prices dont overlap
        coefficient = cor.calculate_coefficient(self.mock_base_prices, self.mock_correlated_different_dates)
        self.assertTrue(coefficient < 1, "Coefficient should be None.")

    @patch('mt5_correlation.mt5.MetaTrader5')
    def test_get_ticks(self, mock):
        """
        Test that caching works. For the purpose of this test, we can use price data rather than tick data.
        Mock 2 different sets of prices. Get three times. Base, One within cache threshold and one outside. Set 1
        should match set 2 but differ from set 3.
        :param mock:
        :return:
        """

        # Correlation class to test
        cor = correlation.Correlation()

        # Mock the tick data to contain 2 different sets. Then get twice. They should match as the data was cached.
        mock.copy_ticks_range.side_effect = [self.mock_base_prices, self.mock_correlated_prices]
        base_ticks = cor.get_ticks('SYMBOL1', None, None, cache_time=3)
        cached_ticks = cor.get_ticks('SYMBOL1', None, None, cache_time=3)
        self.assertTrue(base_ticks.equals(cached_ticks),
                        "Both sets of tick data should match as set 2 came from cache.")

        # Wait 3 seconds
        time.sleep(3)

        # Retrieve again. This one should be different as the cache has expired.
        non_cached_ticks = cor.get_ticks('SYMBOL1', None, None, cache_time=3)
        self.assertTrue(not base_ticks.equals(non_cached_ticks),
                        "Both sets of tick data should differ as cached data had expired.")

    @patch('mt5_correlation.mt5.MetaTrader5')
    def test_start_monitor(self, mock):
        """
        Test that starting the monitor and running for 2 seconds produces two sets of coefficint history when using an
        interval of 1 second.
        :param mock:
        :return:
        """
        # Mock symbol return values
        mock.symbols_get.return_value = self.mock_symbols

        # Correlation class
        cor = correlation.Correlation()

        # Calculate for price data. We should have 100% matching dates in sets. Get prices should be called 3 times.
        # We dont have a SYMBOL2 as this is set as not visible. All pairs should be correlated for the purpose of this
        # test.
        mock.copy_rates_range.side_effect = [self.mock_base_prices, self.mock_correlated_prices,
                                             self.mock_correlated_prices]

        cor.calculate(date_from=self.start_date, date_to=self.end_date, timeframe=5, min_prices=100,
                      max_set_size_diff_pct=100, overlap_pct=100, max_p_value=1)

        # We will build some tick data for each symbol and patch it in. Tick data will be from 10 seconds ago to now.
        # We only need to patch in one set of tick data for each symbol as it will be cached.
        columns = ['time', 'ask']
        starttime = datetime.now() - timedelta(seconds=10)
        tick_data_s1 = pd.DataFrame(columns=columns)
        tick_data_s3 = pd.DataFrame(columns=columns)
        tick_data_s4 = pd.DataFrame(columns=columns)

        now = datetime.now()
        price_base = 1
        while starttime < now:
            tick_data_s1 = tick_data_s1.append(pd.DataFrame(columns=columns, data=[[starttime, price_base * 0.5]]))
            tick_data_s3 = tick_data_s1.append(pd.DataFrame(columns=columns, data=[[starttime, price_base * 0.1]]))
            tick_data_s4 = tick_data_s1.append(pd.DataFrame(columns=columns, data=[[starttime, price_base * 0.25]]))
            starttime = starttime + timedelta(milliseconds=10*random.randint(0, 100))
            price_base += 1

        # Patch it in
        mock.copy_ticks_range.side_effect = [tick_data_s1, tick_data_s3, tick_data_s4]

        # Start the monitor. Run every second. Use ~10 and ~5 seconds of data. Were not testing the overlap and price
        # data quality metrics here as that is set elsewhere so these can be set to not take effect. Set cache level
        # high and don't use autosave. Timer runs in a separate thread so test can continue after it has started.
        cor.start_monitor(interval=1, calculate_from=[0.66, 0.33], min_prices=0, max_set_size_diff_pct=0,
                          overlap_pct=0, max_p_value=1, cache_time=100, autosave=False)

        # Wait 2 seconds so timer runs twice
        time.sleep(2)

        # Stop the monitor
        cor.stop_monitor()

        # We should have 2 coefficients calculated for each symbol pair for each date_from value, so 12 in total.
        self.assertEqual(len(cor.coefficient_history.index), 12)

        # We should have 2 coefficients calculated for a single symbol pair and timeframe
        self.assertEqual(len(cor.get_coefficient_history('SYMBOL1', 'SYMBOL2', 0.66)), 2,
                         "We should have 2 history records for SYMBOL1:SYMBOL2 using the 0.66 min timeframe.")

    @patch('mt5_correlation.mt5.MetaTrader5')
    def test_load_and_save(self, mock):
        """Calculate and run monitor for a few seconds. Store the data. Save it, load it then compare against stored
        data."""

        # Correlation class
        cor = correlation.Correlation()

        # Patch symbol and price data, then calculate
        mock.symbols_get.return_value = self.mock_symbols
        mock.copy_rates_range.side_effect = [self.mock_base_prices, self.mock_correlated_prices,
                                             self.mock_correlated_prices]
        cor.calculate(date_from=self.start_date, date_to=self.end_date, timeframe=5, min_prices=100,
                      max_set_size_diff_pct=100, overlap_pct=100, max_p_value=1)

        # Patch the tick data
        columns = ['time', 'ask']
        starttime = datetime.now() - timedelta(seconds=10)
        tick_data_s1 = pd.DataFrame(columns=columns)
        tick_data_s3 = pd.DataFrame(columns=columns)
        tick_data_s4 = pd.DataFrame(columns=columns)
        now = datetime.now()
        price_base = 1
        while starttime < now:
            tick_data_s1 = tick_data_s1.append(pd.DataFrame(columns=columns, data=[[starttime, price_base * 0.5]]))
            tick_data_s3 = tick_data_s1.append(pd.DataFrame(columns=columns, data=[[starttime, price_base * 0.1]]))
            tick_data_s4 = tick_data_s1.append(pd.DataFrame(columns=columns, data=[[starttime, price_base * 0.25]]))
            starttime = starttime + timedelta(milliseconds=10 * random.randint(0, 100))
            price_base += 1
        mock.copy_ticks_range.side_effect = [tick_data_s1, tick_data_s3, tick_data_s4]

        # Start monitor and run for a seconds with a 1 second interval to produce some coefficient history. Then stop
        # the monitor
        cor.start_monitor(interval=1, calculate_from=0.66, min_prices=0, max_set_size_diff_pct=0,
                          overlap_pct=0, max_p_value=1, cache_time=100, autosave=False)
        time.sleep(2)
        cor.stop_monitor()

        # Get copies of data that will be saved.
        cd_copy = cor.coefficient_data
        pd_copy = cor.get_price_data('SYMBOL1')
        mtd_copy = cor.get_ticks('SYMBOL1', cache_only=True)
        ch_copy = cor.coefficient_history

        # Save, reset data, then reload
        cor.save("unittest.cpd")
        cor.load("unittest.cpd")

        # Test that the reloaded data matches the original
        self.assertTrue(cd_copy.equals(cor.coefficient_data),
                        "Saved and reloaded coefficient data should match original.")
        self.assertTrue(pd_copy.equals(cor.get_price_data('SYMBOL1')),
                        "Saved and reloaded price data should match original.")
        self.assertTrue(mtd_copy.equals(cor.get_ticks('SYMBOL1', cache_only=True)),
                        "Saved and reloaded tick data should match original.")
        self.assertTrue(ch_copy.equals(cor.coefficient_history),
                        "Saved and reloaded coefficient history should match original.")

        # Cleanup. delete the file
        os.remove("unittest.cpd")


if __name__ == '__main__':
    unittest.main()
