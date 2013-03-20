import os
import sys
import warnings
import time
import MySQLdb as sql
import sqlite3 
import numpy as np
import Tkinter as tk
import tkFont
import tkMessageBox
import matplotlib as mpl
import matplotlib.pyplot as plt
from getpass import getuser
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.widgets import Lasso
from PIL import ImageTk,Image
import scipy.spatial as spatial

#---------type definitions-----------#

BASE = {
    "colors":("blue","black"),
    "state":"base",
    "repr":"Base",
    "db_value":np.nan
    }

VIEWED = {
    "colors":("magenta","black"),
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

#---------DB constants------------#        
USER       = getuser()
DBHOST     = "134.104.64.64"
DBNAME     = "Eff_survey"
DBUSER     = "dchampion"
DBPASSWD   = "dchampion"
BASE_QUERY = ("SELECT * FROM Results " 
              "LEFT JOIN Observations ON (Results.OID=Observations.OID) " 
              "LEFT JOIN Beams ON (Results.BID=Beams.BID) "
              "LEFT OUTER JOIN Classification ON (Results.RID=Classification.RID)")
BASE_INSERT = "REPLACE INTO Classification (User,RID,Class) VALUES"
               
DEFAULT_CONDITIONS = "PEACE_score > -12 AND Sigma_opt > 7.0 AND DM_opt > 2.0"#"PEACE_score > -12 AND Sigma_opt > 5.0 AND DM_opt > 2.0"
DEFAULT_LIMIT      = "50000"#"300" 

#---------Known Pulsar DB---------#
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

PSRSQL_DB_ENV = "DP2_KNOWN_PULSARS"
PSRSQL_DB = find_known_pulsar_db()

#---------Plotting constants------#
DEFAULT_XAXIS   = "P_bary_opt"
DEFAULT_YAXIS   = "PEACE_score"
PLOTABLE_FIELDS = [
    'P_disc','F_disc','P_bary_opt','F_opt','Pd_bary_opt',
    'Pdd_bary_opt','P_topo_opt','Pd_topo_opt','Pdd_topo_opt',
    'DM_disc','DM_opt','Epoch_topo','Epoch_bary','Red_chi2',
    'Sigma_disc','Sigma_opt','Noise_prob','SNR','z','r','Power_coh',
    'Power_incoh','Nhits','Nharms','Qual_strength','Qual_width',
    'Qual_width_tree','Qual_persist','Qual_persist_tree','Qual_band',
    'Qual_band_tree','Qual_dm_shape','Qual_dm_smear','Qual_score',
    'Qual_score_tree','PEACE_score','Az','El','RA_deg','Decl_deg',
    'GLong','GLat'
    ]
PLOT_SIZE = (8,5)

class NavSelectToolbar(NavigationToolbar2TkAgg): 
    def __init__(self, canvas,root,parent):
        self.canvas = canvas
        self.root   = root
        self.parent = parent
        font = tkFont.Font(weight="bold",underline=True)
        NavigationToolbar2TkAgg.__init__(self, canvas,root)

        style = {"bg":"darkblue","fg":"gray90"}
        self.lasso_button = self._custom_button(text="lasso",command=lambda: self.lasso(
                lambda inds: self.parent.multi_select_callback(inds),"lasso"),**style)
        self.pick_button = self._custom_button(text="select",command=lambda: self.picker(
                lambda ind: self.parent.single_select_callback(ind),"select"),**style )

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
        self.root.wm_title("HTRU-North candidate viewer (DP2)")
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
        self.db_options_frame = tk.Frame(self.bottom_frame)
        self.db_options_frame.pack(side=tk.LEFT,fill=tk.BOTH)
        self.plotter    = GUIPlotter(self.plot_frame,self)
        self.options    = GUIOptions(self.options_frame,self)
        self.stats      = GUIStats(self.stats_frame,self)
        self.db_options = GUIOptionsDB(self.db_options_frame,self)

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
        
        self.misc_opts_frame = tk.Frame(self.root,pady=20)
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
            self.ax_opts_frame,text="Replot",command=self.parent.plotter.plot,padx=2,pady=2)
        self.replot_button.pack(side=tk.BOTTOM,fill=tk.X,expand=1)
        self.mode_var = tk.StringVar()
        self.mode_var.set("view")
        self._add_select_mode("RFI",RFI) 
        self._add_select_mode("Mark",HIGHLIGHT)
        self._add_select_mode("Reset",BASE)
        self._add_select_mode("View",VIEWED)
        self.toggle_buttons = {}
        for type_dict in TYPES:
            self._add_toggle_mode(self.view_toggle_frame,type_dict)

        self.update_button = self._custom_button(
            self.misc_opts_frame,"Update database",
            self.update_db)

        self.dump_button = self._custom_button(
            self.misc_opts_frame,"Dump plot data",
            self.dump)
        
        self.quit_button = self._custom_button(
            self.misc_opts_frame,"Quit DP2",
            self.quit)

    def dump(self):
        if self.parent.plotter.data_manager is None:return
        dump_name = time.strftime("%Y%m%d-%H%M-DP2.npy")
        np.save(dump_name,self.parent.plotter.data_manager)
        tkMessageBox.showinfo("DP2","%s\nwritten to disk" % dump_name)
        
    def update_db(self):
        data_manager = self.parent.plotter.data_manager
        if data_manager is None:return       
        if tkMessageBox.askokcancel("DP2","Update database?"):
            db_manager = DBManager()
            built_insert = db_manager.build_insert(data_manager.odata)
            db_manager.execute_insert(built_insert)

    def quit(self):
        msg = "Quitting:\nUnsaved progress will be lost.\nDo you wish to Continue?"
        if tkMessageBox.askokcancel("DP2",msg):
            self.parent.root.destroy()

    def _custom_button(self,root,text,command,**kwargs):
        button = tk.Button(root, text=text,
            command=command,padx=2, pady=6,height=1, width=15,**kwargs)
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
        val = state["state"]
        tk.Radiobutton(
            self.mode_select_frame,text=name,
            variable=self.mode_var,value=val,indicatoron=False,
            padx = 2, pady = 6
            ).pack(side=tk.LEFT,fill=tk.X,expand=1)

    def _create_axis_opts(self,frame,name,key_var,scale_var):
        tk.Label(frame,text=name,padx=8,pady=2).pack(side=tk.LEFT,expand=1)
        selector  = tk.OptionMenu(frame,key_var,*PLOTABLE_FIELDS)
        selector.pack(side=tk.LEFT,expand=1)
        selector.configure(width=15)
        check_button = tk.Checkbutton(
            frame,text="Log",variable=scale_var,
            onvalue='log',offvalue='linear')
        check_button.pack(side=tk.LEFT,expand=1)
        return selector,check_button

class GUIOptionsDB(object):
    def __init__(self,root,parent):
        self.root = root
        self.parent = parent
        self.top_frame = tk.Frame(self.root)
        self.top_frame.pack(side=tk.TOP,anchor=tk.W)
        self.bottom_frame = tk.Frame(self.root)
        self.bottom_frame.pack(side=tk.BOTTOM,fill=tk.BOTH,expand=1)
        font = tkFont.Font(weight="bold")
        tk.Label(self.top_frame,text="Conditions:",padx=8,pady=2,height=1,font=font).pack(side=tk.LEFT,anchor=tk.W)
        self.query_entry = tk.Entry(self.top_frame,width=90,bg="white",
                                    fg="black",highlightcolor="black",
                                    highlightthickness=4)
        self.query_entry.pack(side=tk.LEFT,fill=tk.BOTH,expand=1,anchor=tk.W)
        tk.Button(self.top_frame,text="Clear",command=lambda:self.query_entry.delete(0,tk.END)
                  ).pack(side=tk.LEFT,fill=tk.BOTH,expand=1,anchor=tk.W)
        
        tk.Label(self.top_frame,text="Limit:",padx=8,pady=2,height=1,font=font).pack(side=tk.LEFT,anchor=tk.W)
        self.limit_entry = tk.Entry(self.top_frame,width=10,bg="white",
                                    fg="black",highlightcolor="black",
                                    highlightthickness=4)
        self.limit_entry.pack(side=tk.LEFT,expand=1,anchor=tk.W)
        self.submit_button = tk.Button(self.bottom_frame,text="Submit query",command=self.send_query)
        self.submit_button.pack(side=tk.RIGHT,fill=tk.BOTH,expand=1,anchor=tk.E)
        self.mode = tk.StringVar()
        self.mode.set("unclassified")
        tk.Radiobutton(self.bottom_frame,text="Any",variable=self.mode,value="any"
                       ).pack(side=tk.RIGHT,fill=tk.BOTH,expand=1,anchor=tk.E)
        tk.Radiobutton(self.bottom_frame,text="Unclassified",variable=self.mode,value="unclassified"
                       ).pack(side=tk.RIGHT,fill=tk.BOTH,expand=1,anchor=tk.E)
        self.query_entry.insert(0,DEFAULT_CONDITIONS)
        self.limit_entry.insert(0,DEFAULT_LIMIT)
        
    def send_query(self):
        limit = self.limit_entry.get()
        if not limit.isdigit():
            tkMessageBox.showerror("Query error","Given limit is not a numeric value")
            return
        limit = int(limit)
        query = self.query_entry.get()
        mode  = self.mode.get()
        db_manager = DBManager()
        built_query = db_manager.build_query(query,view_mode=mode,limit=limit)
        db_manager.execute_query(built_query)
        output = db_manager.get_output()
        if output is None:
            tkMessageBox.showwarning("DP2","No results returned from query.")
        else:
            data_manager = DataManager(output)
            self.parent.plotter.set_data_manager(data_manager)

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
        self.master_frame = tk.Frame(self.root)
        self.master_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.options_frame = tk.Frame(self.master_frame)
        self.options_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)
        self.image_frame = tk.Frame(self.master_frame)
        self.image_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)
        style = {"fg":"gray90","bg":"darkblue"}
        self._custom_button("Class 1",lambda: self.set_state_wrapper(CLASS1),tk.TOP,**style)
        self._custom_button("Class 2",lambda: self.set_state_wrapper(CLASS2),tk.TOP,**style)
        self._custom_button("RFI",lambda: self.set_state_wrapper(RFI),tk.TOP,**style)
        self._custom_button("Known",lambda: self.set_state_wrapper(KNOWN),tk.TOP,**style)
        self._custom_button("No class",lambda: self.set_state_wrapper(BASE),tk.TOP,**style)
        if PSRSQL_DB:
            tk.Button(master=self.options_frame, text="Is known?",
                      padx=6,pady=10, command=self.find_nearby_knowns,
                      fg="gray90",bg="darkgreen").pack(side=tk.TOP,fill=tk.X)
        self._custom_button("Close",self.root.destroy,tk.BOTTOM,fg="gray90",bg="darkred")
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
        path  = datum["Path"]
        basename = os.path.join(path,os.path.splitext(datum["PS_file"])[0])
        return basename+".gif"

    def display(self):
        gif = self._get_gif_path()
        im = Image.open(gif).rotate(-90)
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
            tkMessageBox.showinfo("Known pulsar finder","No nearby pulsars")
        else:
            self.known_pulsars_window = KnownPulsarDisplay(pulsars,cand)

class KnownPulsarDisplay(object):
    def __init__(self,pulsars,cand):
        self.cand = cand
        self.root = tk.Toplevel()
        tk.Label(self.root,text = "%d nearby pulsars found"%(pulsars.size),
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
            width=70)
        self.listbox.pack(side=tk.LEFT,fill=tk.BOTH,expand=1)
        self.scrollbar.config(command=self.listbox.yview)
        self.scrollbar.pack(side=tk.RIGHT,fill=tk.Y)
        for pulsar in pulsars:
            self.listbox.insert(tk.END,self._details(pulsar))

    def _details(self,pulsar):
        
        print "Cand GL,GB:",self.cand["GLong"],self.cand["GLat"]
        detail = "Name: %s    Period (s): %.8f    DM: %.1f    Offset (deg): %.5f"%(
            pulsar["PSRJ"],pulsar["P0"],pulsar["DM"],
            self._get_offset(pulsar))
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
        style = {"bg":"darkblue","fg":"gray75","padx":2,"pady":2}
        self.navigation_frame = tk.Frame(self.root)
        self.navigation_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=1)
        self.next_button = tk.Button(self.navigation_frame,text="Next",command=self.next,**style) 
        self.next_button.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)
        self.prev_button = tk.Button(self.navigation_frame,text="Previous",command=self.previous,**style)
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
        print state
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

class DBManager(BaseDBManager):
    def __init__(self):
        super(DBManager,self).__init__()

    def connect(self):
        return sql.connect(host=DBHOST,db=DBNAME,user=DBUSER,passwd=DBPASSWD)

    def build_query(self,conditions,view_mode="unclassified",limit=None):
        """Take a partial sql string and build a query."""
        query = "%s WHERE %s"%(BASE_QUERY,conditions)
        if view_mode == "unclassified":
            query = "%s AND Class IS NULL"%(query)
        if limit is not None:
            query = "%s LIMIT %d"%(query,limit)
        query+=";"
        return query
    
    def build_insert(self,cdata):
        """Build the Classification INSERT command.""" 
        rows_to_insert = []
        for row in cdata:
            if not np.isnan(row["db_value"]):
                rows_to_insert.append("(%r,%d,%.1f)"%(
                        USER, row["RID"], row["db_value"]))
        insert_str = ",".join(rows_to_insert)
        insert = "%s %s;"%(BASE_INSERT,insert_str)
        return insert

class KnownPulsarFinder(BaseDBManager):
    def __init__(self):
        super(KnownPulsarFinder,self).__init__()

    def connect(self):
        return sqlite3.connect(PSRSQL_DB)

    def _form_condition(self,key,value,tolerance):
        upper = value+tolerance
        lower = value-tolerance
        contition = "%s > %f AND %s < %f"%(key,lower,key,upper)
        return contition

    def build_query(self,cand,radius=5):
        conditions = []
        #period = cand["P_bary_opt"]
        #ptolerance = period*0.01
        conditions.append(self._form_condition("GL",cand["GLong"],radius))
        conditions.append(self._form_condition("GB",cand["GLat"],radius))
        conditions_str = " AND ".join(conditions)
        query = "SELECT * FROM PSRs WHERE %s;"%(conditions_str)
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

def main():
    root = tk.Tk()
    root.wm_title("HTRU-North candidate viewer (DP2)")
    root.tk_setPalette(background='gray75', foreground='black')
    plotter = GUIMain(root)
    root.mainloop()

if __name__ == "__main__":
    main()
    
            
        



