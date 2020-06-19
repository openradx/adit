import wx
from excel_reader import ExcelReader

#reader = ExcelReader('sample.xlsx')
#reader.open()
#reader.close()

class TabFindPatientIds(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
       # p = wx.Panel(self)
        button = wx.Button(self, -1, "Fill Patient IDs")
        
class TabLog(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        text = wx.TextCtrl(self, -1, "",style=wx.TE_MULTILINE|wx.HSCROLL)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(text, 1, wx.EXPAND|wx.ALL, 5)
        self.SetSizer(sizer)
        

class MainFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="DICOM Fetcher",size=(500,300))
        
        p = wx.Panel(self)
        nb = wx.Notebook(p)
        
        tab1 = TabFindPatientIds(nb)
        #tab2 = TabLog(nb)
        
        nb.AddPage(tab1, "Patient ID")
        #nb.AddPage(tab2, "Log")

        sizer = wx.BoxSizer()
        sizer.Add(nb, 1, wx.EXPAND)
        p.SetSizer(sizer)
        
app = wx.App()
frame = MainFrame()
frame.Show()
app.MainLoop()