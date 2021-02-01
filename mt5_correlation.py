# Gets all symbols from MetaTrader5 market watch and calculates correlation for all pairs

from datetime import datetime, timedelta
import pytz
import math
import pandas as pd
import MetaTrader5 as mt5
from scipy.stats.stats import pearsonr

# connect to MetaTrader 5
if not mt5.initialize():
    print("initialize() failed")
    mt5.shutdown()

# Print connection status
print(mt5.terminal_info())

# get data on MetaTrader 5 version
print(mt5.version())

# Iterate symbols and get those in market watch.
symbols = mt5.symbols_get()
selected_symbols = []
for symbol in symbols:
    if symbol.visible:
        selected_symbols.append(symbol)

# Print symbol counts
total_symbols = mt5.symbols_total()
num_selected_symbols = len(selected_symbols)
print(f"{num_selected_symbols} of {total_symbols} available symbols in Market Watch.")

# Get price data for selected symbols. 1 week of 15 min OHLC data for each symbol. Add to dict.
price_data = {}
# set time zone to UTC to avoid local offset issues, and get from and to dates (a week ago to today)
timezone = pytz.timezone("Etc/UTC")
utc_to = datetime.now(tz=timezone)
utc_from = utc_to - timedelta(days=7)

# get 15 min bars from all selected symbols for 7 days
print(f"Getting prices for all selected symbols.")
for symbol in selected_symbols:
    prices = mt5.copy_rates_range(symbol.name, mt5.TIMEFRAME_M15, utc_from, utc_to)
    print(f"{len(prices)} prices retrieved for {symbol.name}.")

    # Create dataframe from data and convert time in seconds to datetime format
    prices_dataframe = pd.DataFrame(prices)
    prices_dataframe['time'] = pd.to_datetime(prices_dataframe['time'], unit='s')

    # Store prices in dict
    price_data[symbol.name] = prices_dataframe

# Calculate correlation coefficients for all pair combinations.

# Loop through all symbol pair combinations and calculate coefficient. Make sure you don't double count pairs
# eg. (USD/GBP AUD/USD vs AUD/USD USD/GBP). Use grid of all symbols with i and j axis. j starts at i + 1 to
# avoid duplicating. We will store all coefficients in a dataframe for export as CSV.
columns = ['Symbol 1', 'Symbol 2', 'Coefficient', 'UTC Date From', 'UTC Date To', 'Interval']
coefficients = pd.DataFrame(columns=columns)

index = 0
# There will be (x^2 - x) / 2 pairs where x is number of symbols
num_pair_combinations = int((len(selected_symbols) ** 2 - len(selected_symbols)) / 2)

for i in range(0, len(selected_symbols)):
    symbol1 = selected_symbols[i]

    for j in range(i + 1, len(selected_symbols)):
        symbol2 = selected_symbols[j]
        index += 1
        print(f"Calculating coefficients for pair {index} of {num_pair_combinations}: {symbol1.name}:{symbol2.name}.")

        # Get price data for both symbols
        symbol1_price_data = price_data[symbol1.name]
        symbol2_price_data = price_data[symbol2.name]

        # Calculate size of intersection and determine if prices for symbols have enough overlapping timestamps for
        # correlation coefficient calculation to be meaningful. Is the smallest set at least 90% of the size of the
        # largest set and is the overlap set size at least 90% the size of the smallest set?
        intersect_dates = (set(symbol1_price_data['time']) & set(symbol2_price_data['time']))
        len_smallest_set = int(min([len(symbol1_price_data.index), len(symbol2_price_data.index)]))
        len_largest_set = int(max([len(symbol1_price_data.index), len(symbol2_price_data.index)]))
        similar_size = len_largest_set * .9 <= len_smallest_set
        enough_overlap = len(intersect_dates) >= len_smallest_set * .9
        suitable = similar_size and enough_overlap

        if suitable:
            # Calculate coefficient on close prices

            # First filter prices to only include those that intersect
            symbol1_price_data_filtered = symbol1_price_data[symbol1_price_data['time'].isin(intersect_dates)]
            symbol2_price_data_filtered = symbol2_price_data[symbol2_price_data['time'].isin(intersect_dates)]

            # Calculate coefficient. Only use if p value is < 0.01 (highly likely that coefficient is valid and null
            # hypothesis is false).
            coefficient_with_p_value = pearsonr(symbol1_price_data_filtered['close'],
                                                symbol2_price_data_filtered['close'])
            coefficient = None if coefficient_with_p_value[1] > 0.01 else coefficient_with_p_value[0]

            # If not NaN or None round it and store in coefficients dict
            if coefficient is not None and math.isnan(coefficient):
                print("No coefficient calculated. NaN returned.")
            elif coefficient is None:
                print("No coefficient calculated. None returned.")
            else:
                coefficients = coefficients.append({'Symbol 1': symbol1.name, 'Symbol 2': symbol2.name,
                                                    'Coefficient': coefficient, 'UTC Date From': utc_from,
                                                    'UTC Date To': utc_to, 'Interval': 'M15'}, ignore_index=True)
        else:
            print(
                f"Symbol pair {symbol1.name}:{symbol2.name} is not suitable for coefficient calculation. "
                f"Min: {len_smallest_set} Max: {len_largest_set} Overlap {len(intersect_dates)}")

# Sort, highest correlated first
coefficients = coefficients.sort_values('Coefficient', ascending=False)

# Save as CSV
filename = f"Coefficients from {utc_from:%Y%m%d %H%M%S} to {utc_to:%Y%m%d %H%M%S} at M15.csv"
print(f"Saving coefficients as '{filename}'.")
coefficients.to_csv(filename, index=False)

# shut down connection to the MetaTrader 5 terminal
mt5.shutdown()
