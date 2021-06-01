import logging
import pandas as pd
import wx
import wx.grid

from mt5_correlation import correlation as cor
import mt5_correlation.gui.mdi as mdi

# Columns for coefficient table
COLUMN_INDEX = 0
COLUMN_SYMBOL1 = 1
COLUMN_SYMBOL2 = 2
COLUMN_BASE_COEFFICIENT = 3
COLUMN_DATE_FROM = 4
COLUMN_DATE_TO = 5
COLUMN_TIMEFRAME = 6
COLUMN_LAST_CALCULATION = 7
COLUMN_STATUS = 8


class MDIChildStatus(mdi.CorrelationMDIChild):
    """
    Shows the status of all correlations that are within the monitoring threshold
    """

    # The table and grid containing the status of correlations. Defined at instance level to enable refresh.
    __table = None
    __grid = None

    # Number of rows. Required for and updated by refresh method
    __rows = 0

    __log = None  # The logger

    def __init__(self, parent):
        # Super
        wx.MDIChildFrame.__init__(self, parent=parent, id=wx.ID_ANY, title="Correlation Status",
                                  size=wx.Size(width=440, height=-1), style=wx.DEFAULT_FRAME_STYLE)

        # Create logger
        self.__log = logging.getLogger(__name__)

        # Panel and sizer for table
        panel = wx.Panel(self, wx.ID_ANY)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)

        # Create the correlations grid. This is a data table using pandas dataframe for underlying data. Add the
        # correlations_grid to the correlations sizer.
        self.__table = _DataTable(columns=self.GetMDIParent().cor.filtered_coefficient_data.columns)
        self.__grid = wx.grid.Grid(panel, wx.ID_ANY)
        self.__grid.SetTable(self.__table, takeOwnership=True)
        self.__grid.EnableEditing(False)
        self.__grid.EnableDragRowSize(False)
        self.__grid.EnableDragColSize(True)
        self.__grid.EnableDragGridSize(True)
        self.__grid.SetSelectionMode(wx.grid.Grid.SelectRows)
        self.__grid.SetRowLabelSize(0)
        self.__grid.SetColSize(COLUMN_INDEX, 0)  # Index. Hide
        self.__grid.SetColSize(COLUMN_SYMBOL1, 100)  # Symbol 1
        self.__grid.SetColSize(COLUMN_SYMBOL2, 100)  # Symbol 2
        self.__grid.SetColSize(COLUMN_BASE_COEFFICIENT, 100)  # Base Coefficient
        self.__grid.SetColSize(COLUMN_DATE_FROM, 0)  # UTC Date From. Hide
        self.__grid.SetColSize(COLUMN_DATE_TO, 0)  # UTC Date To. Hide
        self.__grid.SetColSize(COLUMN_TIMEFRAME, 0)  # Timeframe. Hide.
        self.__grid.SetColSize(COLUMN_LAST_CALCULATION, 0)  # Last Calculation. Hide
        self.__grid.SetColSize(COLUMN_STATUS, 100)  # Status
        self.__grid.SetMinSize((420, 500))
        sizer.Add(self.__grid, 1, wx.ALL | wx.EXPAND)

        # Bind row doubleclick
        self.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self.__on_doubleckick_row, self.__grid)

        # Refresh to populate
        self.refresh()

    def refresh(self):
        """
        Refreshes grid. Notifies if rows have been added or deleted.
        :return:
        """
        self.__log.debug(f"Refreshing grid.")

        # Update data
        self.__table.data = self.GetMDIParent().cor.filtered_coefficient_data.copy()

        # Format
        self.__table.data.loc[:, 'Base Coefficient'] = self.__table.data['Base Coefficient'].map('{:.5f}'.format)
        self.__table.data.loc[:, 'Last Calculation'] = pd.to_datetime(self.__table.data['Last Calculation'], utc=True)
        self.__table.data.loc[:, 'Last Calculation'] = \
            self.__table.data['Last Calculation'].dt.strftime('%d-%m-%y %H:%M:%S')

        # Start refresh
        self.__grid.BeginBatch()

        # Check if num rows in dataframe has changed, and send appropriate APPEND or DELETE messages
        cur_rows = len(self.GetMDIParent().cor.filtered_coefficient_data.index)
        if cur_rows < self.__rows:
            # Data has been deleted. Send message
            msg = wx.grid.GridTableMessage(self.__table, wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED,
                                           self.__rows - cur_rows, self.__rows - cur_rows)
            self.__grid.ProcessTableMessage(msg)
        elif cur_rows > self.__rows:
            # Data has been added. Send message
            msg = wx.grid.GridTableMessage(self.__table, wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED,
                                           cur_rows - self.__rows)  # how many
            self.__grid.ProcessTableMessage(msg)

        self.__grid.EndBatch()

        # Send updated message
        msg = wx.grid.GridTableMessage(self.__table, wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES)
        self.__grid.ProcessTableMessage(msg)

        # Update row count
        self.__rows = cur_rows

    def __on_doubleckick_row(self, evt):
        """
        Open the graphs when a row is doubleclicked.
        :param evt:
        :return:
        """
        row = evt.GetRow()
        symbol1 = self.__grid.GetCellValue(row, COLUMN_SYMBOL1)
        symbol2 = self.__grid.GetCellValue(row, COLUMN_SYMBOL2)

        mdi.FrameManager.open_frame(parent=self.GetMDIParent(),
                                    frame_module='mt5_correlation.gui.mdi_child_correlationgraph',
                                    frame_class='MDIChildCorrelationGraph',
                                    raise_if_open=True,
                                    symbols=[symbol1, symbol2])


class _DataTable(wx.grid.GridTableBase):
    """
    A data table that holds data in a pandas dataframe. Contains highlighting rules for status.
    """
    data = None  # The data for this table. A Pandas DataFrame

    def __init__(self, columns):
        wx.grid.GridTableBase.__init__(self)
        self.headerRows = 1
        self.data = pd.DataFrame(columns=columns)

    def GetNumberRows(self):
        return len(self.data)

    def GetNumberCols(self):
        return len(self.data.columns) + 1

    def GetValue(self, row, col):
        if row < self.RowsCount and col < self.ColsCount:
            return self.data.index[row] if col == 0 else self.data.iloc[row, col - 1]
        else:
            raise Exception(f"Trying to access row {row} and col {col} which does not exist.")

    def SetValue(self, row, col, value):
        self.data.iloc[row, col - 1] = value

    def GetColLabelValue(self, col):
        if col == 0:
            if self.data.index.name is None:
                return 'Index'
            else:
                return self.data.index.name
        return str(self.data.columns[col - 1])

    def GetTypeName(self, row, col):
        return wx.grid.GRID_VALUE_STRING

    def GetAttr(self, row, col, prop):
        attr = wx.grid.GridCellAttr()

        # Check that we are not out of bounds
        if row < self.RowsCount:
            # If column is status, check and highlight if diverging or converging.
            if col in [COLUMN_STATUS]:
                # Is status one of interest
                value = self.GetValue(row, col)
                if value != "":
                    if value in [cor.STATUS_DIVERGING]:
                        attr.SetBackgroundColour(wx.RED)
                    elif value in [cor.STATUS_CONVERGING]:
                        attr.SetBackgroundColour(wx.GREEN)
                    else:
                        attr.SetBackgroundColour(wx.WHITE)

        return attr
