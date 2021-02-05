from datetime import datetime, timedelta
import logging.config
import pandas as pd
import pytz
import yaml
from mt5_correlation.mt5 import MT5
from mt5_correlation.correlation import Correlation
import definitions

# Configure logger
with open(fr'{definitions.ROOT_DIR}\logging_conf.yaml', 'rt') as file:
    config = yaml.safe_load(file.read())
    logging.config.dictConfig(config)
    log = logging.getLogger()

# Create mt5 class. This contains required methods for interacting with MT5.
mt5 = MT5()

# Gte all visible symbols
symbols = mt5.get_symbols()

# set time zone to UTC to avoid local offset issues, and get from and to dates (a week ago to today)
timezone = pytz.timezone("Etc/UTC")
utc_to = datetime.now(tz=timezone)
utc_from = utc_to - timedelta(days=7)

# Set timeframe
timeframe = mt5.TIMEFRAME_M15

# Get price data for selected symbols. 1 week of 15 min OHLC data for each symbol. Add to dict.
price_data = {}
for symbol in symbols:
    price_data[symbol.name] = mt5.get_prices(symbol=symbol, from_date=utc_from, to_date=utc_to,
                                             timeframe=timeframe)

# Loop through all symbol pair combinations and calculate coefficient. Make sure you don't double count pairs
# eg. (USD/GBP AUD/USD vs AUD/USD USD/GBP). Use grid of all symbols with i and j axis. j starts at i + 1 to
# avoid duplicating. We will store all coefficients in a dataframe for export as CSV.
columns = ['Symbol 1', 'Symbol 2', 'Coefficient', 'UTC Date From', 'UTC Date To', 'Timeframe']
coefficients = pd.DataFrame(columns=columns)

index = 0
# There will be (x^2 - x) / 2 pairs where x is number of symbols
num_pair_combinations = int((len(symbols) ** 2 - len(symbols)) / 2)

for i in range(0, len(symbols)):
    symbol1 = symbols[i]

    for j in range(i + 1, len(symbols)):
        symbol2 = symbols[j]
        index += 1

        # Get price data for both symbols
        symbol1_price_data = price_data[symbol1.name]
        symbol2_price_data = price_data[symbol2.name]

        # Get coefficient and store if valid
        coefficient = Correlation.calculate_coefficient(symbol1_prices=symbol1_price_data,
                                                        symbol2_prices=symbol2_price_data, max_set_size_diff_pct=90,
                                                        overlap_pct=90, max_p_value=0.05)

        if coefficient is not None:
            coefficients = coefficients.append({'Symbol 1': symbol1.name, 'Symbol 2': symbol2.name,
                                                'Coefficient': coefficient, 'UTC Date From': utc_from,
                                                'UTC Date To': utc_to, 'Timeframe': timeframe}, ignore_index=True)

            log.info(f"Pair {index} of {num_pair_combinations}: {symbol1.name}:{symbol2.name} has a coefficient of "
                     f"{coefficient}.")
        else:
            log.info(f"Coefficient for pair {index} of {num_pair_combinations}: {symbol1.name}:{symbol2.name} could not"
                     f" be calculated.")

# Sort, highest correlated first
coefficients = coefficients.sort_values('Coefficient', ascending=False)

# Save as CSV
filename = f"Coefficients from {utc_from:%Y%m%d %H%M%S} to {utc_to:%Y%m%d %H%M%S}.csv"
log.info(f"Saving coefficients as '{filename}'.")
coefficients.to_csv(filename, index=False)
