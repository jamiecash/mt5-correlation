import definitions
import markdown
import wx
import wx.html

import mt5_correlation.gui.mdi as mdi


class MDIChildHelp(mdi.CorrelationMDIChild):
    """
    Shows the README.md file
    """

    def __init__(self, parent):
        # Super
        mdi.CorrelationMDIChild.__init__(self, parent=parent, id=wx.ID_ANY, pos=wx.DefaultPosition, title="Help",
                                         size=wx.Size(width=800, height=-1),
                                         style=wx.DEFAULT_FRAME_STYLE)

        # Panel and sizer for help file
        panel = wx.Panel(self, wx.ID_ANY)
        sizer = wx.BoxSizer()
        panel.SetSizer(sizer)

        # HtmlWindow
        html_widget = wx.html.HtmlWindow(parent=panel, id=wx.ID_ANY, style=wx.html.HW_SCROLLBAR_AUTO | wx.html.HW_NO_SELECTION)
        sizer.Add(html_widget, 1, wx.ALL | wx.EXPAND)

        # Load the help file, convert markdown to HTML and display. The markdown library doesnt understand the shell
        # format so we will remove.
        markdown_text = open(definitions.HELP_FILE).read()
        markdown_text = markdown_text.replace("```shell", "```")
        html = markdown.markdown(markdown_text)
        html_widget.SetPage(html)

    def refresh(self):
        """
        Nothing to do on refresh. Help file doesnt change during outside of development.
        :return:
        """
        pass
