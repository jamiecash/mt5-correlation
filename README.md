# mt5-correlation
Calculates correlation coefficient between all symbols in MetaTrader5 Market Watch and monitors previously correlated symbol pairs for divergence

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
python -m mt5_correlations/mt5_correlations.py
```

This will open a GUI.

## Calculating Baseline Coefficients
On the first time that you run, you will want to calculate the initial set of correlations.
1) Open settings and review the settings under the 'Calculate' tab. These settings are:
    - from.days: The number of days of data to be used to calculate the coefficient.
    - timeframe: The timeframe for price candles to use for the calculation. Possible values are:
        * 1: 1 Minute candles
        * 2: 2 Minute candles
        * 3: 3 Minute candles
        * 4: 4 Minute candles
        * 5: 5 Minute candles
        * 6: 6 Minute candles
        * 10: 10 Minute candles
        * 15: 15 Minute candles
        * 20: 20 Minute candles
        * 30: 30 Minute candles
        * 16385: 1 Hour candles
        * 16386: 2 Hour candles
        * 16387: 3 Hour candles
        * 16388: 4 Hour candles
        * 16390: 6 Hour candles
        * 16392: 8 Hour candles
        * 16396: 12 Hour candles
        * 16408: 1 Day candles
        * 32769: 1 Week candles
        * 49153: 1 Month candles
        
    - min_prices: The minimum number of candles required to calculate a coefficient from. If any of the symbols do not have at least this number of candles then the coefficient won't be calculated.
    - max_set_size_diff_pct: For a meaningful coefficient calculation, the two sets of data should be of a similar size. This setting specifies the % difference allowed for a correlation to be calculated. The smallest set of candle data must be at least this values % of the largest set.
    - overlap_pct: The dates and times in the two sets of data must match. The coefficient will only be calculated against the dates that overlap. Any non overlapping dates will be discarded. This setting specifies the minimum size of the overlapping data when compared to the smallest set as a %. A coefficient will not be calculated if this threshold is not met.
    - max_p_value: The maximum P value for the coefficient to be considered valid. A full explanation on the correlation coefficient P value is available here: https://docs.scipy.org/doc/scipy-0.14.0/reference/generated/scipy.stats.pearsonr.html.
    
2) Set the threshold for the correlations to monitor. This can be set under the Settings 'Monitoring' tab and is named monitoring.threshold. Only settings with a coefficient over this threshold will be displayed and monitored.

3) Calculate the coefficients by selecting File/Calculate. All symbol pairs that have a correlation coefficient greater than the monitoring threshold will be displayed. A graph showing the price candle data used to calculate the coefficient for the pair will be displayed when you select the row. 

4) You may want to save. Select File/Save and choose a file name. This file will contain all the calculated coefficients, and the price data used to calculate them. This file can be loaded to avoid having to recalculate the baseline coefficients every time you use the application.

## Monitoring for Divergence
Once you have calculated or loaded the baseline coefficients, they can be monitored for divergence.
1) Open settings and review the settings under the 'Monitor' tab. These settings are:
    - from.minutes: The number of minutes of data to be used to calculate the coefficient.
    - interval: The number of seconds between monitoring events. The application will monitor for divergence every {interval} seconds.
    - min_prices: Tick data will be converted to 1 second candles prior to calculation. This will enable data to be matched between symbols. This setting specifies the minimum number of price candles required to calculate a coefficient from. If any of the symbols do not have at least number of candles then the coefficient won't be calculated.
    - max_set_size_diff_pct: For a meaningful coefficient calculation, the two sets of data should be of a similar size. This setting specifies the % difference allowed for a correlation to be calculated. The smallest set of price candles must be at least this values % of the largest set.
    - overlap_pct: The dates and times in the two sets of data must match. The ticks will be converted to 1 second price candles before calculation. The coefficient will only be calculated against the times from the candles that overlap. Any non overlapping times will be discarded. This setting specifies the minimum size of the overlapping data when compared to the smallest set as a %. A coefficient will not be calculated if this threshold is not met.
    - max_p_value: The maximum P value for the coefficient to be considered valid. A full explanation on the correlation coefficient P value is available here: https://docs.scipy.org/doc/scipy-0.14.0/reference/generated/scipy.stats.pearsonr.html.
    - monitoring_threshold: The application will only display correlated pairs that have a correlation coefficient greater than or equal to this value.
    - divergence_threshold: The application will consider a pair to have diverged if the correlation coefficient falls below this threshold. These will be highlighted in yellow.
    - tick_cache_time: Every calculation requires tick data for both symbols. Tick data will be cached for this number of seconds before being retrieved from MetaTrader. Some caching is recommended as a single monitoring run will request the same data for symbols that form multiple correlated pairs.
    - autosave: Whether to auto save after every monitoring event. If a file was opened or has been saved, then the data will be saved to this file, otherwise the data will be saved to a file named autosave.cpd.
    
2) Switch the monitoring toggle to on. The application will continuously monitor for divergence. The data frame will be updated with the last time that the correlation was checked, and the last coefficient. The chart frame will contain 5 charts which will be updated after every monitoring event:
    - 2 charts, one for each symbol in the correlated pair, showing the price data used to calculate the baseline coefficient.
    - 2 charts, one for each symbol in the correlated pair, showing the tick data used to calculate the latest coefficient.
    - 1 chart showing every correlation coefficient calculated for the symbol pair.