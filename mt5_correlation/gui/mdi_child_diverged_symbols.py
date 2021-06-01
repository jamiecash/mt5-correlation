import logging
import pandas as pd
import wx
import wx.grid

import mt5_correlation.gui.mdi as mdi

# Columns for diverged symbols table
COLUMN_INDEX = 0
COLUMN_SYMBOL = 1
COLUMN_NUM_DIVERGENCES = 2


class MDIChildDivergedSymbols(mdi.CorrelationMDIChild):
    """
    Shows the status of all correlations that are within the monitoring threshold
    """

    # The table and grid containing the symbols that form part of the diverged correlations. Defined at instance level
    # to enable refresh.
    __table = None
    __grid = None

    # Number of rows. Required for and updated by refresh method
    __rows = 0

    __log = None  # The logger

    def __init__(self, parent):
        # Super
        wx.MDIChildFrame.__init__(self, parent=parent, id=wx.ID_ANY, title="Diverged Symbols",
                                  size=wx.Size(width=240, height=-1), style=wx.DEFAULT_FRAME_STYLE)

        # Create logger
        self.__log = logging.getLogger(__name__)

        # Panel and sizer for table
        panel = wx.Panel(self, wx.ID_ANY)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)

        # Create the grid. This is a data table using pandas dataframe for underlying data. Add the
        # grid to the sizer.
        self.__table = _DataTable(columns=self.GetMDIParent().cor.diverged_symbols.columns)
        self.__grid = wx.grid.Grid(panel, wx.ID_ANY)
        self.__grid.SetTable(self.__table, takeOwnership=True)
        self.__grid.EnableEditing(False)
        self.__grid.EnableDragRowSize(False)
        self.__grid.EnableDragColSize(True)
        self.__grid.EnableDragGridSize(True)
        self.__grid.SetSelectionMode(wx.grid.Grid.SelectRows)
        self.__grid.SetRowLabelSize(0)
        self.__grid.SetColSize(COLUMN_INDEX, 0)  # Index. Hide
        self.__grid.SetColSize(COLUMN_SYMBOL, 100)  # Symbol
        self.__grid.SetColSize(COLUMN_NUM_DIVERGENCES, 100)  # Num divergences
        self.__grid.SetMinSize((220, 100))
        sizer.Add(self.__grid, 1, wx.ALL | wx.EXPAND)

        # Refresh to populate
        self.refresh()

    def refresh(self):
        """
        Refreshes grid. Notifies if rows have been added or deleted.
        :return:
        """
        self.__log.debug(f"Refreshing grid.")

        # Update data
        self.__table.data = self.GetMDIParent().cor.diverged_symbols.copy()

        # Start refresh
        self.__grid.BeginBatch()

        # Check if num rows in dataframe has changed, and send appropriate APPEND or DELETE messages
        cur_rows = len(self.GetMDIParent().cor.diverged_symbols.index)
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


class _DataTable(wx.grid.GridTableBase):
    """
    A data table that holds data in a pandas dataframe.
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

        return attr
