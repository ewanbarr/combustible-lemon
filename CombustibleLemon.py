import os
import sys
import glob
import warnings
import time
import MySQLdb as sql
import sqlite3 
import tempfile
import numpy as np
import Tkinter as tk
import tkFont
import tkMessageBox
import tkFileDialog
import matplotlib as mpl
import matplotlib.pyplot as plt
from getpass import getuser
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.widgets import Lasso
from PIL import ImageTk,Image
import scipy.spatial as spatial

#---------Usable colors--------------#
# These colors are implemented in both matplotlib and tkinter
"""
gold,yellow,pink,tomato,aquamarine,orange,cyan,gray,goldenrod,turquoise,
lavender,maroon,thistle,navy,blue,linen,snow,red,bisque,khaki,salmon,
gainsboro,coral,purple,azure
"""

#---------type definitions-----------#

BASE = {
    "colors":("blue","white"),
    "state":"base",
    "repr":"Base",
    "db_value":np.nan
    }

VIEWED = {
    "colors":("purple","white"),
    "state":"viewed",
    "repr":"Viewed",
    "db_value":4.0
    }

RFI = {
    "colors":("red","black"),
    "state":"rfi",
    "repr":"RFI",
    "db_value":5.0
    }
    
HIGHLIGHT = {
    "colors":("green","black"),
    "state":"highlight",
    "repr":"Marked",
    "db_value":np.nan
    }

CLASS1 = {
    "colors":("orange","black"),
    "state":"class1",
    "repr":"Class 1",
    "db_value":1.0
    } 

CLASS2 = {
    "colors":("yellow","black"),
    "state":"class2",
    "repr":"Class 2",
    "db_value":2.0
    }

KNOWN = {
    "colors":("cyan","black"),
    "state":"known",
    "repr":"Known",
    "db_value":6.0
    }

TYPES = [BASE,
         VIEWED,
         RFI,
         HIGHLIGHT,
         CLASS1,
         CLASS2,
         KNOWN]

MODE_TO_TYPE = {
    "rfi":RFI,
    "highlight":HIGHLIGHT,
    "base":BASE
    }

#---------Known Pulsar DB---------#
#as there is no position information in the bestprof file.
#we search based on period and DM (no harmonic matching)

def find_known_pulsar_db():
    guess = "known_pulsars.sql"
    path = None
    if os.path.isfile(guess):
        path = guess
    env_path = os.getenv(PSRSQL_DB_ENV)
    if env_path is not None:
        if os.path.isfile(env_path):
            path = env_path
    if path is None:
        msg = ("No known pulsar database ('psrcat_sqlite.db') "
               "found in current path and no %r environment set.\n"
               "Known pulsar checking will be disabled.\n\n")
        warnings.warn(msg % PSRSQL_DB_ENV,Warning)
        return None
    else:
        return path

PSRSQL_DB_ENV = "CL_KNOWN_PULSARS"
PSRSQL_DB = find_known_pulsar_db()

#---------Plotting constants------#
DEFAULT_XAXIS   = "P_bary (ms)"
DEFAULT_YAXIS   = "Sigma"
BESTPROF_DTYPE  = [
    ('Best DM',"float32"),('Epoch_bary',"float32"),
    ('Epoch_topo',"float32"),("P''_bary (s/s^2)","float32"),
    ("P''_topo (s/s^2)","float32"),("P'_bary (s/s)","float32"),
    ("P'_topo (s/s)","float32"),('P_bary (ms)',"float32"),
    ('P_topo (ms)',"float32"),('Sigma',"float32"),
    ('Reduced chi-sqr',"float32"),('PFD_file',"|S400")
    ]
PLOTABLE_FIELDS = [key for key,dtype in BESTPROF_DTYPE if dtype=="float32"]
PLOT_SIZE = (8,5)
MPL_STYLE = {
    "text.color":"lightblue",
    "axes.labelcolor":"lightblue",
    "axes.edgecolor":"black",
    "axes.facecolor":"0.4",
    "xtick.color": "lightblue",
    "ytick.color": "lightblue",
    "figure.facecolor":"black",
    "figure.edgecolor":"black"
}

mpl.rcParams.update(MPL_STYLE)


#----------Style options---------#
DEFAULT_PALETTE = {"foreground":"lightblue","background":"black"}
DEFAULT_STYLE_1 = {"foreground":"black","background":"lightblue"}
DEFAULT_STYLE_2 = {"foreground":"gray90","background":"darkgreen"}
DEFAULT_STYLE_3 = {"foreground":"gray90","background":"darkred"}

class NavSelectToolbar(NavigationToolbar2TkAgg): 
    def __init__(self, canvas,root,parent):
        self.canvas = canvas
        self.root   = root
        self.parent = parent
        font = tkFont.Font(weight="bold",underline=True)
        NavigationToolbar2TkAgg.__init__(self, canvas,root)
        self.lasso_button = self._custom_button(text="lasso",command=lambda: self.lasso(
                lambda inds: self.parent.multi_select_callback(inds),"lasso"),**DEFAULT_STYLE_1)
        self.pick_button = self._custom_button(text="select",command=lambda: self.picker(
                lambda ind: self.parent.single_select_callback(ind),"select"),**DEFAULT_STYLE_1)

    def _custom_button(self, text, command, **kwargs):
        button = tk.Button(master=self, text=text, padx=2, pady=2, command=command, **kwargs)
        button.pack(side=tk.LEFT,fill="y")
        return button

    def contains_points(self,verts,callback):
        xys = self.parent.xy
        if xys is not None:
            p = mpl.path.Path(verts)
            ind = [ii for ii,xy in enumerate(xys) if p.contains_point(xy)]
            callback(ind)
        self.canvas.draw_idle()
        del self.lasso_obj
            
    def press_lasso(self,event,callback):
        if event.inaxes is None: return
        self.lasso_obj = Lasso(event.inaxes, (event.xdata, event.ydata),
                           lambda verts: self.contains_points(verts,callback))

    def press_picker(self,event,callback):
        ind = event.ind
        if ind: callback(event.ind[0])
        
    def _disconnect_all_ids(self):
        self.canvas.widgetlock.release(self)
        if self._idPress is not None:
            self._idPress = self.canvas.mpl_disconnect(self._idPress)
            self.mode = ''
        if self._idRelease is not None:
            self._idRelease = self.canvas.mpl_disconnect(self._idRelease)
            self.mode = ''
        
    def lasso(self,callback,msg):
        self._active = "LASSO"
        self._disconnect_all_ids()
        self._idPress = self.canvas.mpl_connect(
            'button_press_event', lambda event: self.press_lasso(event,callback))
        self.mode = msg
        self.canvas.widgetlock(self)
        for a in self.canvas.figure.get_axes():
            a.set_navigate_mode(self._active)
        self.set_message(self.mode)
        
    def picker(self,callback,msg):
        self._active = "PICKER"
        self._disconnect_all_ids()
        self._idPress = self.canvas.mpl_connect(
            'pick_event', lambda event: self.press_picker(event,callback))
        self.mode = msg
        for a in self.canvas.figure.get_axes():
            a.set_navigate_mode(self._active)
        self.set_message(self.mode)
    
      
class GUIMain(object):
    def __init__(self,root):
        self.root = root
        self.root.wm_title("Combustible Lemon (PRESTO version)")
        self.top_frame = tk.Frame(self.root)
        self.top_frame.pack(side=tk.TOP) 
        self.bottom_frame = tk.Frame(self.root)
        self.bottom_frame.pack(side=tk.BOTTOM)
        self.stats_frame = tk.Frame(self.top_frame)
        self.stats_frame.pack(side=tk.LEFT)
        self.plot_frame = tk.Frame(self.top_frame)
        self.plot_frame.pack(side=tk.LEFT)
        self.options_frame = tk.Frame(self.top_frame) 
        self.options_frame.pack(side=tk.LEFT)
        self.cands_options_frame = tk.Frame(self.bottom_frame)
        self.cands_options_frame.pack(side=tk.LEFT,fill=tk.BOTH)
        self.plotter    = GUIPlotter(self.plot_frame,self)
        self.options    = GUIOptions(self.options_frame,self)
        self.stats      = GUIStats(self.stats_frame,self)
        self.cand_opts  = GUIOptionsCands(self.cands_options_frame,self)

class GUIPlotter(object):
    def __init__(self,root,parent):
        self.root = root
        self.parent = parent
        self.figure = plt.Figure(figsize=PLOT_SIZE, dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(bottom=0.15,right=0.95,top=0.95)
        self.canvas = FigureCanvasTkAgg(self.figure,self.root)
        self.toolbar = NavSelectToolbar(self.canvas,self.root,self)
        self.toolbar.update()
        self.plot_widget = self.canvas.get_tk_widget()
        self.plot_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.toolbar.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.xy = None
        self.data_manager = None
        self.active_viewers = {}
        self.active_multi_viewer = None
        self.toolbar.pick_button.invoke()
        self.canvas.show()

    def set_data_manager(self,data_manager):
        self.data_manager = data_manager
        self.plot()

    def plot(self,**kwargs):
        if self.data_manager is None:return
        self.data_manager.toggle_types(self.parent.options.toggle_buttons)
        self.ax.cla()
        x_field  = self.parent.options.xaxis_key_var.get()
        y_field  = self.parent.options.yaxis_key_var.get()
        xscale = self.parent.options.xaxis_scale_var.get()
        yscale = self.parent.options.yaxis_scale_var.get()
        x = self.data_manager.cdata[x_field]
        y = self.data_manager.cdata[y_field]
        if x.min() <= 0.0 and xscale == "log":
            self.parent.options.xaxis_scale_check.invoke()
            xscale = self.parent.options.xaxis_scale_var.get()
        if y.min() <= 0.0 and yscale == "log":
            self.parent.options.yaxis_scale_check.invoke()
            yscale = self.parent.options.yaxis_scale_var.get()
        self.xy = np.vstack((x,y)).transpose()
        self.ax.set_xscale(xscale)
        self.ax.set_yscale(yscale)
        self.ax.set_xlabel(x_field)
        self.ax.set_ylabel(y_field)
        self.current_plot = self.ax.scatter(x,y,picker=True,**kwargs)
        self.update_colors()
        self.canvas.show()

    def update_colors(self):
        if self.data_manager is None:return
        self.current_plot.set_facecolors(self.data_manager.cdata["facecolor"])
        self.current_plot.set_edgecolors(self.data_manager.cdata["edgecolor"])
        self.canvas.show()

    def multi_select_callback(self,inds):
        if self.data_manager is None:return
        if not inds:return
        mode = self.parent.options.mode_var.get()
        if mode == "viewed":
            self.launch_multi_viewer(inds)
        else:
            state = MODE_TO_TYPE[mode]
            self.set_state(inds,state)
            
    def single_select_callback(self,ind):
        if self.data_manager is None:return
        mode = self.parent.options.mode_var.get()
        if mode == "viewed":
            self.launch_viewer(ind)
        else:
            state = MODE_TO_TYPE[mode]
            self.set_state(ind,state)
        
    def set_state(self,inds,state):
        if self.data_manager is None:return
        self.data_manager.set_cdata("facecolor", inds, state["colors"][0])
        self.data_manager.set_cdata("edgecolor", inds, state["colors"][1])
        self.data_manager.set_cdata("db_value", inds, state["db_value"])
        self.data_manager.set_cdata("state", inds, state["state"])
        self.update_colors()

    def launch_viewer(self,ind):
        if self.data_manager is None:return
        if ind in self.active_viewers.keys():
            self.active_viewers[ind].root.destroy()
        self.active_viewers[ind] = GUIViewerSingle(self,ind)
        
    def launch_multi_viewer(self,inds):
        if self.data_manager is None:return
        self.active_multi_viewer = GUIViewerMulti(self,inds)
   

class GUIOptions(object):
    def __init__(self,root,parent):
        self.root = root
        self.parent = parent
        self.mode_select_frame = tk.Frame(self.root,pady=20)
        self.mode_select_frame.pack(side=tk.TOP,fill=tk.X,expand=1)
        self.ax_opts_frame = tk.Frame(self.root)
        self.ax_opts_frame.pack(side=tk.TOP,expand=1)
        self.view_toggle_frame = tk.Frame(self.root,pady=20)
        self.view_toggle_frame.pack(side=tk.TOP,fill=tk.X,expand=1)
        
        self.misc_opts_frame = tk.Frame(self.root,pady=10)
        self.misc_opts_frame.pack(side=tk.TOP,fill=tk.X,expand=1)
                
        self.xaxis_frame = tk.Frame(self.ax_opts_frame)
        self.xaxis_frame.pack(side=tk.TOP,expand=1)
        self.yaxis_frame = tk.Frame(self.ax_opts_frame)
        self.yaxis_frame.pack(side=tk.TOP,expand=1)
        self.xaxis_scale_var = tk.StringVar()
        self.yaxis_scale_var = tk.StringVar()
        self.xaxis_key_var   = tk.StringVar()
        self.yaxis_key_var   = tk.StringVar()
        self.xaxis_scale_var.set("log")
        self.yaxis_scale_var.set("linear")
        self.xaxis_key_var.set(DEFAULT_XAXIS)
        self.yaxis_key_var.set(DEFAULT_YAXIS)
        self.xaxis_selector,self.xaxis_scale_check = self._create_axis_opts(
            self.xaxis_frame,"X-Axis:",self.xaxis_key_var,self.xaxis_scale_var)
        self.yaxis_selector,self.yaxis_scale_check = self._create_axis_opts(
            self.yaxis_frame,"Y-Axis:",self.yaxis_key_var,self.yaxis_scale_var)
        self.replot_button = tk.Button(
            self.ax_opts_frame,text="Replot",command=self.parent.plotter.plot,
            padx=2, pady=6, **DEFAULT_STYLE_2)
        self.replot_button.pack(side=tk.BOTTOM,fill=tk.X,expand=1)
        self.mode_var = tk.StringVar()
        self.mode_var.set("viewed")
        self._add_select_mode("RFI",RFI) 
        self._add_select_mode("Mark",HIGHLIGHT)
        self._add_select_mode("Reset",BASE)
        self._add_select_mode("View",VIEWED)
        self.toggle_buttons = {}
        for type_dict in TYPES:
            self._add_toggle_mode(self.view_toggle_frame,type_dict)

        self.update_button = self._custom_button(
            self.misc_opts_frame,"Print Class 1/2",
            self.update_db,**DEFAULT_STYLE_1)

        self.dump_button = self._custom_button(
            self.misc_opts_frame,"Dump plot data",
            self.dump,**DEFAULT_STYLE_1)
        
        self.quit_button = self._custom_button(
            self.misc_opts_frame,"Quit",
            self.quit,**DEFAULT_STYLE_3)

    def dump(self):
        if self.parent.plotter.data_manager is None:return
        dump_name = tkFileDialog.asksaveasfilename()
        if dump_name:
            np.save(dump_name,self.parent.plotter.data_manager)
        
    def update_db(self):
        data_manager = self.parent.plotter.data_manager
        if data_manager is None:return       
        cdata = data_manager.cdata
        class1_id = np.where(cdata["state"]=="class1")
        class2_id = np.where(cdata["state"]=="class2")
        print "######## Class 1 #########"
        for row in cdata[class1_id]:
            print row["PFD_file"]
        print "######## Class 2 #########"
        for row in cdata[class2_id]:
            print row["PFD_file"]

    def quit(self):
        msg = "Quitting:\nUnsaved progress will be lost.\nDo you wish to Continue?"
        if tkMessageBox.askokcancel("Combustible Lemon",msg):
            self.parent.root.destroy()

    def _custom_button(self,root,text,command,**kwargs):
        button = tk.Button(root, text=text,
            command=command,padx=2, pady=2,height=1, width=15,**kwargs)
        button.pack(side=tk.TOP,fill=None,expand=1)
        return button

    def _add_toggle_mode(self,frame,type_info):
        name = type_info["state"]
        text = type_info["repr"]
        colors = type_info["colors"]
        self.toggle_buttons[name] = {}
        var = tk.StringVar()
        var.set("on")
        check_button = tk.Checkbutton(
            frame,text=text,variable=var,
            onvalue="off",offvalue="on",
            indicatoron=False,
            activeforeground=colors[0],
            activebackground=colors[1],
            background = colors[0],
            foreground = colors[1],
            selectcolor = "gray75",
            width=10)
        check_button.pack(side=tk.TOP,expand=1)
        self.toggle_buttons[name]["button"]   = check_button
        self.toggle_buttons[name]["variable"] = var

    def _add_select_mode(self,name,state):
        val  = state["state"]
        tk.Radiobutton(
            self.mode_select_frame,text=name,
            variable=self.mode_var,value=val,indicatoron=False,
            padx = 2, pady = 6,selectcolor="gray50",**DEFAULT_STYLE_1
            ).pack(side=tk.LEFT,fill=tk.X,expand=1)

    def _create_axis_opts(self,frame,name,key_var,scale_var):
        tk.Label(frame,text=name,padx=8,pady=2).pack(side=tk.LEFT,expand=1)
        selector  = tk.OptionMenu(frame,key_var,*PLOTABLE_FIELDS)
        selector.pack(side=tk.LEFT,expand=1)
        selector.configure(width=15,**DEFAULT_STYLE_1)
        check_button = tk.Checkbutton(
            frame,text="Log",variable=scale_var,
            onvalue='log',offvalue='linear',selectcolor="black")
        check_button.pack(side=tk.LEFT,expand=1)
        return selector,check_button

class GUIOptionsCands(object):
    def __init__(self,root,parent):
        self.root = root
        self.parent = parent
        self.top_frame = tk.Frame(self.root)
        self.top_frame.pack(side=tk.TOP,anchor=tk.W)
        self.bottom_frame = tk.Frame(self.root)
        self.bottom_frame.pack(side=tk.BOTTOM,fill=tk.BOTH,expand=1)
        tk.Label(self.top_frame,text="Directory:",padx=8,pady=2,height=1).pack(side=tk.LEFT,anchor=tk.W)
        self.directory_entry = tk.Entry(self.top_frame,width=90,bg="lightblue",
                                    fg="black",highlightcolor="lightblue",insertbackground="black",
                                    highlightthickness=2)
        self.directory_entry.pack(side=tk.LEFT,fill=tk.BOTH,expand=1,anchor=tk.W)
        tk.Button(self.top_frame,text="Browse",command=self.launch_dir_finder,**DEFAULT_STYLE_1
                  ).pack(side=tk.LEFT,fill=tk.BOTH,expand=1,anchor=tk.W)
        self.submit_button = tk.Button(self.bottom_frame,text="Load candidates",width=60,
                                       command=self.send_query,**DEFAULT_STYLE_2)
        self.submit_button.pack(side=tk.BOTTOM,expand=1,anchor=tk.CENTER)
        self.walk_mode = tk.StringVar()
        self.walk_mode.set("off")
        tk.Checkbutton(self.top_frame, text="Follow tree",
                       variable=self.walk_mode, onvalue="on",
                       offvalue="off",padx=6,pady=2,selectcolor="black"
                       ).pack(side=tk.LEFT,fill=tk.BOTH,expand=1)
        
    def send_query(self):
        directory = self.directory_entry.get()
        finder = CandidateFinder()
        mode = self.walk_mode.get()
        if mode == "on":
            finder.get_from_directories(directory)
        else:
            finder.get_from_directory(directory)
        if not finder.filenames:
            tkMessageBox.showwarning("Combustible Lemon","No files found in specified directory.")
        else:
            output = finder.parse_all()
            data_manager = DataManager(output)
            self.parent.plotter.set_data_manager(data_manager)
    
    def launch_dir_finder(self):
        directory = tkFileDialog.askdirectory()
        self.directory_entry.delete(0,tk.END)
        self.directory_entry.insert(0,directory)

class GUIStats(object):
    def __init__(self,root,parent):
        self.parent = parent
        self.root = root

class GUIViewerBase(object):
    def __init__(self,parent):
        self.parent = parent
        self.root = tk.Toplevel()
        self.ind = None
        self.known_pulsars_window = None
        self.gif_temp = None
        self.master_frame = tk.Frame(self.root)
        self.master_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.options_frame = tk.Frame(self.master_frame)
        self.options_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)
        self.image_frame = tk.Frame(self.master_frame)
        self.image_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)
        style = {"fg":"gray90","bg":"darkblue"}
        self._custom_button("Class 1",lambda: self.set_state_wrapper(CLASS1),tk.TOP,**DEFAULT_STYLE_1)
        self._custom_button("Class 2",lambda: self.set_state_wrapper(CLASS2),tk.TOP,**DEFAULT_STYLE_1)
        self._custom_button("RFI",lambda: self.set_state_wrapper(RFI),tk.TOP,**DEFAULT_STYLE_1)
        self._custom_button("Known",lambda: self.set_state_wrapper(KNOWN),tk.TOP,**DEFAULT_STYLE_1)
        self._custom_button("No class",lambda: self.set_state_wrapper(BASE),tk.TOP,**DEFAULT_STYLE_1)
        if PSRSQL_DB:
            tk.Button(master=self.options_frame, text="Is known?",
                      padx=6,pady=10, command=self.find_nearby_knowns,
                      fg="gray90",bg="darkgreen").pack(side=tk.TOP,fill=tk.X)
        self._custom_button("Close",self.root.destroy,tk.BOTTOM,**DEFAULT_STYLE_3)
        self.key_press_callback_dict = {
            'r':lambda:self.set_state_wrapper(RFI),
            '1':lambda:self.set_state_wrapper(CLASS1),
            '2':lambda:self.set_state_wrapper(CLASS2),
            'k':lambda:self.set_state_wrapper(KNOWN),
            'escape':self.root.destroy
            }
        self.root.bind("<Key>", self.key_press_callback)
        
    def _custom_button(self,text,command,side,**kwargs):
        button = tk.Button(master=self.options_frame, text=text, 
                      padx=6, pady=6, command=command,**kwargs)
        button.pack(side=side,fill=tk.BOTH)
        return button
    
    def set_state_wrapper(self,state):
        self.parent.set_state(self.ind,state)

    def _get_gif_path(self):
        datum = self.parent.data_manager.cdata[self.ind]
        gif = "%s.gif" % datum["PFD_file"]
        if not os.path.isfile(gif):
            print "Getting new gif path"
            self.gif_temp = tempfile.NamedTemporaryFile(
                prefix="combustible-lemon-",
                suffix=".gif")
            gif = self.gif_temp.name
            ps_file = "%s.ps" % datum["PFD_file"]
            ps_to_gif(ps_file,gif)
        return gif

    def _del_gif_path(self):
        if self.gif_temp is not None:
            print "Closing",self.gif_temp.name
            self.gif_temp.close()
        
    def display(self):
        gif = self._get_gif_path()
        im = Image.open(gif).rotate(-90)
        self._del_gif_path()
        self.tempim = ImageTk.PhotoImage(im)
        self.gif_label = tk.Label(self.image_frame,image=self.tempim)
        self.gif_label.pack(fill=tk.BOTH, expand=1)
        self.mark_viewed_if_base()
        
    def mark_viewed_if_base(self):
        state = self.parent.data_manager.cdata[self.ind]["state"]
        if state == BASE["state"]:
            self.set_state_wrapper(VIEWED)

    def key_press_callback(self,event):
        char = event.keysym.lower()
        if char in self.key_press_callback_dict.keys():
            self.key_press_callback_dict[char]()

    def find_nearby_knowns(self):
        cand = self.parent.data_manager.cdata[self.ind]
        known_db = KnownPulsarFinder()
        query = known_db.build_query(cand)
        known_db.execute_query(query)
        pulsars = known_db.get_output() 
        if pulsars is None:
            tkMessageBox.showinfo("Known pulsar finder","No similar pulsars")
        else:
            self.known_pulsars_window = KnownPulsarDisplay(pulsars,cand)

class KnownPulsarDisplay(object):
    def __init__(self,pulsars,cand):
        self.cand = cand
        self.root = tk.Toplevel()
        tk.Label(self.root,text = "%d similar pulsars found"%(pulsars.size),
                 pady=6,padx=2).pack(side=tk.TOP,fill=tk.X,expand=1,anchor=tk.W)
        self.close = tk.Button(self.root,text="Close",command=self.root.destroy)
        self.close.pack(side=tk.BOTTOM,expand=1)
        self.pulsars_frame = tk.Frame(self.root)
        self.pulsars_frame.pack(side=tk.BOTTOM,fill=tk.BOTH, expand=1)
        self.scrollbar = tk.Scrollbar(self.pulsars_frame)
        self.scrollbar.pack(side=tk.RIGHT,fill=tk.Y)
        self.listbox = tk.Listbox(
            self.pulsars_frame,
            yscrollcommand=self.scrollbar.set,
            selectbackground="darkblue",
            selectforeground="gray90",
            width=70,
            **DEFAULT_PALETTE)
        self.listbox.pack(side=tk.LEFT,fill=tk.BOTH,expand=1)
        self.scrollbar.config(command=self.listbox.yview)
        self.scrollbar.pack(side=tk.RIGHT,fill=tk.Y)
        for pulsar in pulsars:
            self.listbox.insert(tk.END,self._details(pulsar))

    def _details(self,pulsar):
        detail = "Name: %s    Period (s): %.8f    DM: %.1f    P/P_known: %.5f"%(
            pulsar["PSRJ"],pulsar["P0"],pulsar["DM"],
            self.cand["P_bary (ms)"]/(1000.*pulsar["P0"]))
        return detail

    def _get_offset(self,pulsar):
        gl_offset = self.cand["GLong"]-pulsar["GL"]
        gb_offset = self.cand["GLat"]-pulsar["GB"]
        return np.sqrt(gl_offset**2 + gb_offset**2)

        
class GUIViewerSingle(GUIViewerBase):
    def __init__(self,parent,ind):
        super(GUIViewerSingle,self).__init__(parent)
        self.ind = ind
        self.display()
            
class GUIViewerMulti(GUIViewerBase):
    def __init__(self,parent,inds):
        super(GUIViewerMulti,self).__init__(parent)
        self.inds = inds
        self.ind = inds[0] 
        self.size = len(inds)
        self._position = 0
        self.navigation_frame = tk.Frame(self.root)
        self.navigation_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=1)
        self.next_button = tk.Button(self.navigation_frame,text="Next",
                                     command=self.next,padx=2,pady=2,**DEFAULT_STYLE_1) 
        self.next_button.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)
        self.prev_button = tk.Button(self.navigation_frame,text="Previous",
                                     command=self.previous,padx=2,pady=2,**DEFAULT_STYLE_1)
        self.prev_button.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.selection_frame = tk.Frame(self.master_frame)
        self.selection_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.scrollbar = tk.Scrollbar(self.selection_frame)
        self.selection_listbox = tk.Listbox(
            self.selection_frame,
            yscrollcommand=self.scrollbar.set,
            selectbackground="darkblue",
            selectforeground="gray90",
            width=10)            
        self.selection_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        [self.selection_listbox.insert(tk.END,ii+1) for ii in range(self.size)]
        self.selection_listbox.selection_set(self._position,self._position)
        self.selection_listbox.bind('<<ListboxSelect>>', self.list_select)
        self.scrollbar.config(command=self.selection_listbox.yview)
        self.scrollbar.pack(side=tk.RIGHT,fill=tk.Y)
        self.key_press_callback_dict['right'] = self.next
        self.key_press_callback_dict['left']  = self.previous
        self.key_press_callback_dict['space'] = self.next
        self.selection_listbox.focus_set()
        self.display()

    def update(self):
        self.ind = self.inds[self._position]
        self.selection_listbox.activate(self._position)
        gif = self._get_gif_path()
        im = Image.open(gif).rotate(-90)
        self._del_gif_path()
        self.tempim = ImageTk.PhotoImage(im)
        self.gif_label.configure(image=self.tempim)
        self.selection_listbox.selection_clear(0,self.size)
        self.selection_listbox.selection_set(self._position,self._position)
        self.mark_viewed_if_base()
        
    def list_select(self,event):
        selected = self.selection_listbox.curselection()[0]
        index = int(selected.split()[0])
        self._position = index
        self.update()
        
    def next(self):
        if self._position < self.size-1:
            self._position+=1
            self.update()
            self.selection_listbox.yview_scroll(1,"units")
            
    def previous(self):
        if self._position > 0:
            self._position-=1
            self.update()
            self.selection_listbox.yview_scroll(-1,"units")
            
    def set_state_wrapper(self,state):
        if state["state"] in ["base","viewed"]:
            state_str = ""
        else:
            state_str = state["repr"]
        msg = "%d  %s"%(self._position+1,state_str)
        self.selection_listbox.delete(self._position)
        self.selection_listbox.insert(self._position,msg)
        self.parent.set_state(self.ind,state)
        self.selection_listbox.selection_clear(0,self.size)
        self.selection_listbox.selection_set(self._position,self._position)
        self.selection_listbox.activate(self._position)

class BaseDBManager(object):
    def __init__(self):
        self.cursor = None
        self.connection = None

    def __del__(self):
        if self.connection is not None:
            self.connection.close()
    
    def make_connection(func,*args,**kwargs):
        """Decorator to make data base connections."""
        def wrapped(self,*args,**kwargs):
            try:
                self.connection = self.connect()
                self.cursor = self.connection.cursor()
            except Exception as error:
                self.cursor = None
                warnings.warn(str(error),Warning)
            else:
                func(self,*args,**kwargs)
        return wrapped

    @make_connection
    def execute_query(self,query):
        """Execute a mysql query"""
        print query
        try:
            self.cursor.execute(query)
        except Exception as error:
            warnings.warn(str(error),Warning)

    @make_connection
    def execute_insert(self,insert):
        """Execute a mysql insert"""
        print insert
        try:
            self.cursor.execute(insert)
            self.connection.commit()
        except Exception as error:
            self.connection.rollback()
            warnings.warn(str(error),Warning)

    def fix_duplicate_field_names(self,names):
        """Fix duplicate field names by appending
        an integer to repeated names."""
        used = []
        new_names = []
        for name in names:
            if name not in used:
                new_names.append(name)
            else:
                new_name = "%s_%d"%(name,used.count(name))
                new_names.append(new_name)
            used.append(name)
        return new_names

    def get_output(self):
        """Get sql data in numpy recarray form."""
        if self.cursor.description is None:
            return None
        names = [i[0] for i in self.cursor.description]
        names = self.fix_duplicate_field_names(names)
        try:
            output  = self.cursor.fetchall()
        except Exception as error:
            warnings.warn(str(error),Warning)
            return None
        if not output:
            return None
        output = np.rec.fromrecords(output,names=names)
        return output

class CandidateFinder(object):
    def __init__(self):
        self.filenames = []
        self.counter = None

    def _is_valid(self,pfd):
        ps_valid = os.path.isfile("%s.ps" % pfd)
        bp_valid = os.path.isfile("%s.bestprof" % pfd)
        return all((ps_valid,bp_valid))

    def get_from_directory(self,directory):
        pfds = glob.glob("%s/*.pfd" % directory)
        print "%s/*.pfd" % directory
        if not pfds:
            return None
        for pfd in pfds:
            if self._is_valid(pfd):
                self.filenames.append(pfd)

    def get_from_directories(self,directory):
        counter = 0
        print "Searching %s" % directory
        rambler = os.walk(directory)
        for path,dirnames,filenames in rambler:
            for filename in filenames:
                if filename.endswith(".pfd"):
                    pfd = os.path.join(path,filename)
                    if self._is_valid(pfd):
                        self.filenames.append(pfd)
                        counter+=1
                        sys.stdout.write("Found %d files...\r"%counter)
                        sys.stdout.flush()
                
    def parse_all(self):
        filenames = list(set(self.filenames))
        nfiles = len(filenames)
        recarray = np.recarray(nfiles,dtype=BESTPROF_DTYPE)
        print "Parsing %d .bestprof files..." % nfiles
        for ii,filename in enumerate(filenames):
            if ii%10 == 0:
                sys.stdout.write("%.2f\r"%(100.*ii/nfiles))
                sys.stdout.flush()
            bestprof_file = "%s.bestprof" % filename
            info = parse_bestprof(bestprof_file)
            for key in PLOTABLE_FIELDS:
                recarray[ii][key] = info[key]
            recarray[ii]["PFD_file"] = filename
        return recarray

class KnownPulsarFinder(BaseDBManager):
    def __init__(self):
        super(KnownPulsarFinder,self).__init__()

    def connect(self):
        return sqlite3.connect(PSRSQL_DB)

    def _form_condition(self,key,value,tolerance):
        upper = value+tolerance
        lower = value-tolerance
        contition = "(%s > %f AND %s < %f)"%(key,lower,key,upper)
        return contition

    def build_query(self,cand):
        conditions = []
        period = cand["P_bary (ms)"]/1000.
        ptolerance = period*0.001
        conditions.append(self._form_condition("P0",period,ptolerance))
        conditions.append(self._form_condition("P0",0.5*period,0.5*ptolerance))
        conditions.append(self._form_condition("P0",2.0*period,2.0*ptolerance))
        conditions.append(self._form_condition("P0",4.0*period,4.0*ptolerance))
        conditions_str = " OR ".join(conditions)
        dm = cand["Best DM"]
        dmtolerance = max(10.0,dm*0.15)
        dm_condition = self._form_condition("DM",dm,dmtolerance)
        query = "SELECT * FROM PSRs WHERE (%s) AND %s;"%(conditions_str,dm_condition)
        return query

    def execute_insert(self):
        return None

class DataManager(object):
    def __init__(self,data_array):
        self.odata = data_array
        self.add_field([("size","float")])
        self.add_field([("facecolor","|S20")])
        self.add_field([("edgecolor","|S20")])
        self.add_field([("state","|S20")])
        self.add_field([("odata_id","int32")])
        self.add_field([("db_value","float32")])
        self.odata["size"]   = 1
        self.odata["facecolor"] = BASE["colors"][0]
        self.odata["edgecolor"] = BASE["colors"][1]
        self.odata["state"] = BASE["state"]
        self.odata["db_value"] = BASE["db_value"]
        self.odata["odata_id"] = np.arange(self.odata.size)
        self._original_data = self.odata.copy()
        self.soft_reset()
    
    def hard_reset(self):
        self.odata = self._original_data.copy()
        self.soft_reset()

    def soft_reset(self):
        self.cdata = self.odata
        
    def add_field(self,descr):
        """Add a field to the recarray."""
        new_odata = np.empty(self.odata.shape, dtype=self.odata.dtype.descr + descr)
        for name in self.odata.dtype.names:
            new_odata[name] = self.odata[name]
        self.odata = new_odata

    def toggle_types(self,toggle_opts):
        size = self.odata.size
        inds = np.zeros(shape=size,dtype=np.bool)
        for type_dict in TYPES:
            if toggle_opts[type_dict["state"]]["variable"].get() == "on":
                inds[(self.odata["state"]==type_dict["state"])] = True
        self.cdata = self.odata[inds]

    def set_cdata(self,field,inds,val):
        self.cdata[field][inds] = val
        odata_inds = self.cdata[inds]["odata_id"] 
        self.odata[field][odata_inds] = val

def ps_to_gif(infile,outfile):
    os.system("convert -density 80 %s -trim -flatten %s"%(infile,outfile))

def parse_bestprof(filename):
    f = open(filename,"r")
    lines = f.readlines()
    f.close()
    info = {} 
    for ii,line in enumerate(lines):
        if not line.startswith("# "):
            continue
        if line.startswith("# Prob(Noise)"):
            line = line[2:].split("<")
        else:
            line = line[2:].split("=")
            
        key = line[0].strip()
        value = line[1].strip()
        
        if "+/-" in value:
            value = value.split("+/-")[0]
            if "inf" in value:
                value = "0.0"

        if value == "N/A":
            value = "0.0"

        if "Epoch" in key:
            key = key.split()[0]

        if key == "Prob(Noise)":
            key = "Sigma"
            try:
                value = value.split("(")[1].split()[0].strip("~")
            except:
                value = "30.0"
                    
        info[key]=value
    return info
        
def parse_pfd(filename):
    header_params = [
        "ndms","nperiods","npdots","nsubs","nparts","proflen","nchans","pstep"
        ,"pdstep","dmstep","ndmfact","npfact","filname","candname","telescope","plotdev"
        ,"rastr","decstr","dt","tstart","tend","tepoch","bepoch","avgvoverc","lofreq"
        ,"chan_wid","best_dm","topo_pow","topo_p1","topo_p2","topo_p3","bary_pow","bary_p1"
        ,"bary_p2","bary_p3","fold_pow","fold_p1","fold_p2","fold_p3","orb_p","orb_e","orb_x"
        ,"orb_w","orb_t","orb_pd","orb_wd"
        ]
    f = open(filename,"r")
    values = {}
    count = 0
    for ii in range(12):
        values[header_params[count]] = struct.unpack("I",f.read(4))[0]
        count += 1
    for ii in range(4):
        val_len = struct.unpack("I",f.read(4))[0]
        values[header_params[count]] = ''.join([char for char in struct.unpack("c"*val_len,f.read(val_len))])
        count += 1
    for ii in range(2):
        values[header_params[count]] = ''.join([char for char in struct.unpack("c"*13,f.read(13))])
        f.seek(3,1)
        count += 1
    for ii in range(9):
        values[header_params[count]] = struct.unpack("d",f.read(8))[0]
        count += 1
    for ii in range(3):
        values[header_params[count]] = struct.unpack("f",f.read(4))[0]
        count += 1
        f.seek(4,1)
        for ii in range(3):
            values[header_params[count]] = struct.unpack("d",f.read(8))[0]
            count += 1
    f.close()
    return values

def main():
    root = tk.Tk()
    root.wm_title("Combustible Lemon (PRESTO version)")
    root.tk_setPalette(**DEFAULT_PALETTE)
    plotter = GUIMain(root)
    root.mainloop()

if __name__ == "__main__":
    main()
    
            
        



