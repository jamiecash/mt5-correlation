import unittest
from unittest.mock import patch
import mt5_correlation.mt5 as mt5
import pandas as pd
from datetime import datetime


class Symbol:
    """ A Mock symbol class"""
    name = None
    visible = None

    def __init__(self, name, visible):
        self.name = name
        self.visible = visible


class TestMT5(unittest.TestCase):
    """
    Unit test for MT5. Uses mock to mock MetaTrader5 connection.
    """

    # Mock symbols. 5 Symbols, 4 visible.
    mock_symbols = [Symbol(name='SYMBOL1', visible=True),
                    Symbol(name='SYMBOL2', visible=True),
                    Symbol(name='SYMBOL3', visible=False),
                    Symbol(name='SYMBOL4', visible=True),
                    Symbol(name='SYMBOL5', visible=True)]

    # Mock prices for symbol 1
    mock_prices = pd.DataFrame(columns=['time', 'close'],
                               data=[[datetime(2021, 1, 1, 1, 5, 0), 123.123],
                                     [datetime(2021, 1, 1, 1, 10, 0), 123.124],
                                     [datetime(2021, 1, 1, 1, 15, 0), 123.125],
                                     [datetime(2021, 1, 1, 1, 20, 0), 125.126],
                                     [datetime(2021, 1, 1, 1, 25, 0), 123.127],
                                     [datetime(2021, 1, 1, 1, 30, 0), 123.128]])

    @patch('mt5_correlation.mt5.MetaTrader5')
    def test_get_symbols(self, mock):
        # Mock return value
        mock.symbols_get.return_value = self.mock_symbols

        # Call get_symbols
        symbols = mt5.MT5().get_symbols()

        # There should be four, as one is set as not visible
        self.assertTrue(len(symbols) == 4, "There should be 5 symbols returned from MT5.")

    @patch('mt5_correlation.mt5.MetaTrader5')
    def test_get_prices(self, mock):
        # Mock return value
        mock.copy_rates_range.return_value = self.mock_prices

        # Call get prices
        prices = mt5.MT5().get_prices(symbol='SYMBOL1', from_date='01-JAN-2021 01:00:00',
                                      to_date='01-JAN-2021 01:10:25', timeframe=mt5.TIMEFRAME_M5)

        # There should be 6
        self.assertTrue(len(prices.index) == 6, "There should be 6 prices.")

    @patch('mt5_correlation.mt5.MetaTrader5')
    def test_get_ticks(self, mock):
        # Mock return value
        mock.copy_ticks_range.return_value = self.mock_prices

        # Call get ticks
        ticks = mt5.MT5().get_ticks(symbol='SYMBOL1', from_date='01-JAN-2021 01:00:00', to_date='01-JAN-2021 01:10:25')

        # There should be 6
        self.assertTrue(len(ticks.index) == 6, "There should be 6 prices.")


if __name__ == '__main__':
    unittest.main()


