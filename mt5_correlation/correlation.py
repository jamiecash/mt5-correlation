import math
from scipy.stats.stats import pearsonr


class Correlation:
    """
    A class to calculate the correlation coefficient between two sets of price data
    """

    @staticmethod
    def calculate_coefficient(symbol1_prices, symbol2_prices, max_set_size_diff_pct=90, overlap_pct=90,
                              max_p_value=0.05):
        """
        Calculates the correlation coefficient between two sets of price data. Uses close price.

        :param symbol1_prices:
        :param symbol2_prices:
        :param max_set_size_diff_pct: Correlations will only be calculated if the sizes of the two price data sets are
            within this pct of each other
        :param overlap_pct:
        :param max_p_value: The maximum p value for the correlation to be meaningful
        :return: correlation coefficient, or None if coefficient could not be calculated.
        """
        # Calculate size of intersection and determine if prices for symbols have enough overlapping timestamps for
        # correlation coefficient calculation to be meaningful. Is the smallest set at least max_set_size_diff_pct % of
        # the size of the largest set and is the overlap set size at least overlap_pct % the size of the smallest set?
        coefficient = None

        intersect_dates = (set(symbol1_prices['time']) & set(symbol2_prices['time']))
        len_smallest_set = int(min([len(symbol1_prices.index), len(symbol2_prices.index)]))
        len_largest_set = int(max([len(symbol1_prices.index), len(symbol2_prices.index)]))
        similar_size = len_largest_set * (max_set_size_diff_pct / 100) <= len_smallest_set
        enough_overlap = len(intersect_dates) >= len_smallest_set * (overlap_pct / 100)
        suitable = similar_size and enough_overlap

        if suitable:
            # Calculate coefficient on close prices

            # First filter prices to only include those that intersect
            symbol1_prices_filtered = symbol1_prices[symbol1_prices['time'].isin(intersect_dates)]
            symbol2_prices_filtered = symbol2_prices[symbol2_prices['time'].isin(intersect_dates)]

            # Calculate coefficient. Only use if p value is < 0.01 (highly likely that coefficient is valid and null
            # hypothesis is false).
            coefficient_with_p_value = pearsonr(symbol1_prices_filtered['close'], symbol2_prices_filtered['close'])
            coefficient = None if coefficient_with_p_value[1] >= max_p_value else coefficient_with_p_value[0]

            # If NaN, change to None
            if coefficient is not None and math.isnan(coefficient):
                coefficient = None

        return coefficient



