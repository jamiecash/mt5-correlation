# mt5-correlation
Calculates correlation coefficient between all symbols in MetaTrader5 Market Watch.

# Setup
1) Set up your MetaTrader 5 environment ensuring that all symbols that you would like to assess for correlation are shown in your Market Watch window;
2) Set up your python environment; and
3) Install the required libraries.

```
pip install -r mt5-correlation/requirements.txt
```

# Usage
If you set up a virtual environment in the Setup step, ensure this is activated. Then run the script.

```
python -m mt5_correlations/get_correlations.py
```

A .csv file containing the correlation coefficient for all combinations of sybmols from the MetaTrader market watch will be produced in the current directory.

|Symbol 1    |Symbol 2    |Coefficient|UTC Date From      |UTC Date To        |Timeframe|
|------------|------------|-----------|-------------------|-------------------|---------|
|OIL-MAR21   |OILMn-MAR21 |1.0        |2021-01-29 11:54:29|2021-02-05 11:54:29|15       |
|EURUSD      |EURHKD      |0.99980    |2021-01-29 11:54:29|2021-02-05 11:54:29|15       |
|OILMn-MAR21 |BRENT-APR21 |0.99894    |2021-01-29 11:54:29|2021-02-05 11:54:29|15       |
|OIL-MAR21   |BRENT-APR21 |0.99894    |2021-01-29 11:54:29|2021-02-05 11:54:29|15       |
|GSOIL-FEB21 |BRENT-APR21 |0.99605    |2021-01-29 11:54:29|2021-02-05 11:54:29|15       |
|GSOIL-FEB21 |OILMn-MAR21 |0.99543    |2021-01-29 11:54:29|2021-02-05 11:54:29|15       |
|GSOIL-FEB21 |OIL-MAR21   |0.99543    |2021-01-29 11:54:29|2021-02-05 11:54:29|15       |
|EU50Cash    |FRA40Cash   |0.99072    |2021-01-29 11:54:29|2021-02-05 11:54:29|15       |

# Customising
Edit get_correlations.py to customise.

The coefficients are calculated only if:
* The smallest set of price data is no less than 90% of the size of the largest set;
* The overlapping prices between both sets of price data contains no less than 90% of the prices in the smallest set;
* The pearsonr p-value for the calculated coefficient is less than 0.05.

These settings can all be changed in the call to Correlation.calculate_coefficient by passing values for max_set_size_diff_pct; overlap_pct; or max_p_value.
```
coefficient = Correlation.calculate_coefficient(symbol1_prices=symbol1_price_data,
                                                        symbol2_prices=symbol2_price_data, max_set_size_diff_pct=90,
                                                        overlap_pct=90, max_p_value=0.05)
```

The price data compared is 15 minute price data for the last 7 days. This can be changed by changing the values for the following variables:
```
utc_to = datetime.now(tz=timezone)
utc_from = utc_to - timedelta(days=7)
timeframe = mt5.TIMEFRAME_M15
```

The possible values for timeframe are:

|Timeframe|Description|
|--------------|-----------|
|TIMEFRAME_M1  |1 minute   |
|TIMEFRAME_M2  |2 minutes  |
|TIMEFRAME_M3  |3 minutes  |
|TIMEFRAME_M4  |4 minutes  |
|TIMEFRAME_M5  |5 minutes  |
|TIMEFRAME_M6  |6 minutes  |
|TIMEFRAME_M10 |10 minutes |
|TIMEFRAME_M12 |12 minutes |
|TIMEFRAME_M12 |15 minutes |
|TIMEFRAME_M20 |20 minutes |
|TIMEFRAME_M30 |30 minutes |
|TIMEFRAME_H1  |1 hour     |
|TIMEFRAME_H2  |2 hours    |
|TIMEFRAME_H3  |3 hours    |
|TIMEFRAME_H4  |4 hours    |
|TIMEFRAME_H6  |6 hours    |
|TIMEFRAME_H8  |8 hours    |
|TIMEFRAME_H12 |12 hours   |
|TIMEFRAME_D1  |1 day      |
|TIMEFRAME_W1  |1 week     |
|TIMEFRAME_MN1 |1 month    |