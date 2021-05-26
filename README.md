# mt5-correlation
Calculates correlation coefficient between all symbols in MetaTrader5 Market Watch and monitors previously correlated symbol pairs for divergence

# Setup
1) Set up your MetaTrader 5 environment ensuring that all symbols that you would like to assess for correlation are shown in your Market Watch window;
2) Set up your python environment; and
3) Install the required libraries.

```shell
pip install -r mt5-correlation/requirements.txt
```

# Usage
If you set up a virtual environment in the Setup step, ensure this is activated. Then run the script.

```shell
python -m mt5_correlations/mt5_correlations.py
```

This will open a GUI.

## Calculating Baseline Coefficients
On the first time that you run, you will want to calculate the initial set of correlations.
1) Open settings and review the settings under the 'Calculate' tab. Hover over the individual settings for help.
2) Set the threshold for the correlations to monitor. This can be set under the Settings 'Monitoring' tab and is named 'Monitoring Threshold'. Only settings with a coefficient over this threshold will be displayed and monitored.
3) Calculate the coefficients by selecting File/Calculate. All symbol pairs that have a correlation coefficient greater than the monitoring threshold will be displayed. A graph showing the price candle data used to calculate the coefficient for the pair will be displayed when you select the row.
4) You may want to save. Select File/Save and choose a file name. This file will contain all the calculated coefficients, and the price data used to calculate them. This file can be loaded to avoid having to recalculate the baseline coefficients every time you use the application.

## Monitoring for Divergence
Once you have calculated or loaded the baseline coefficients, they can be monitored for divergence.
1) Open settings and review the settings under the 'Monitor' tab. Hover over the individual settings for help.
2) Switch the monitoring toggle to on. The application will continuously monitor for divergence. The data frame will be updated with the last time that the correlation was checked, and the last coefficient. The chart frame will contain 3 charts which will be updated after every monitoring event:
    - One showing the price history data used to calculate the baseline coefficient for both symbols in the correlated pair;
    - One showing the tick data used to calculate the latest coefficient for both symbols in the correlated pair.
    - One showing every correlation coefficient calculated for the symbol pair.