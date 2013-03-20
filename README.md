combustible-lemon
=================

Tkinter plotting GUI for PRESTO output

Dependencies
------------

 * ImageMagick Command-line Tools (not required if output is not in postscript format)
 * Matplotlib
 * Numpy

Installation
------------

No installation required, however if you wish to run the known pulsar checker then you will need to set an environment variable called CL_KNOWN_PULSARS which points towards combustible lemons known pulsar database ('known_pulsars.sql').

The basics
----------

combustible-lemon (CL) is a light-weight, easily customised (both stylistically and functionally) plotting interface for output of the PRESTO pulsar searching package. It works by traversing given directories and collecting information from the .bestprof files for each candidate (assuming a corresponding .pfd and .ps file exist). This information is then stored in a numpy record array for plotting. CL allows users to quickly visualise the contents of a set of PRESTO folds and interactively select folds to be viewed.

As the Python's main image library, PIL, cannot handle PRESTO format .ps files, the files are converted to gifs using Image Magick's `convert` command-line tool. The file is stored in /tmp/ until it is loaded to the viewer, meaning that only read permisions are required to use the plotter. 

Guide
-----

Start up the plotter using `python combustiblelemon.py`

You should see something like this:

![alt text](https://github.com/ewanbarr/combustible-lemon/blob/master/images/base_window.png?raw=true "Main CL window")

Here the plotting interface is Matplotlib and the rest is all Tkinter. Starting from the top-left corner we have some tools for manipulating the plot:

 * `Home`: Reset plot to default pan/zoom 
 * `Back`: Go back one pan/zoom operation
 * `Forward`: Go forward one pan/zoom operation 
 * `Pan`: Pan the plotted data (click and drag on the plot window)
 * `Zoom`: Zoom on the plotted data (click and drag on the plot window)
 * `Subplot tool`: Adjusts plot edges (No needed, do not use)
 * `Save`: Save the plot as an image
 * `lasso`: Select multiple points with a lasso (click and drag on the plot window) 
 * `select`: Select a single point (click on desired point)

Moving to the right side of the GUI we have tools for choosing what data is to be presented and what to do when a point is selected.

The selection mode determines what happens when one or more points are selected:
    
 * `RFI`: Mark selected candidate(s) as RFI
 * `Mark`: Highlight selected candidate(s) 
 * `Reset`: Reset candidate(s) back to original colour/state
 * `View`: View selected candidate(s) 
 
Going down from the selection modes we have the axis selection options. Here you can select what is plotted on each axis and set log/linear scales on the axis. Here there is also the `Replot` button which does exactly what is says on the tin.

The multicoloured buttons below are toggle buttons for plotting different types. The colours of the buttons are defined by the face and dege colours of the types (defined at the top of the code).

The last three buttons on the right-hand side are:

 * `Print Class 1/2`: Print the top ranked candidates to the terminal
 * `Dump plot data`: Save the plot data as a .npy file
 * `Quit`: Exit the program

Moving to the bottom of the GUI we have the directory searching options:

 * `Directory`: Text entry for the name of the directory to search for candidate files in
 * `Browse`: Open a dialog to search for a desired directory
 * `Follow tree`: Toggle candidate finder to descend through subdirectories in the search for more candidates
 * `Load candidates`: Find and parse all candidates in the search directories
 
Assuming that you have the `select` and `View` buttons toggled, clicking on a candidate will result in something like the following: 

![alt text](https://github.com/ewanbarr/combustible-lemon/blob/master/images/single_viewer.png?raw=true "Single viewer")

Everything is pretty self explanatory here. The buttons on the top right allow set the rank the displayed candidate and the `Close` button closes the window. To speed up the process of going through candidates, this window exports several key bindings:

 * `Class 1` -- "1"
 * `Class 2` -- "2"
 * `RFI`     -- "r"
 * `Known`   -- "k"
 * `Close`   -- "esc"
 
If instead of the `select` button we have the `lasso` button pressed, we can select multiple candidates to view, giving something like:

![alt text](https://github.com/ewanbarr/combustible-lemon/blob/master/images/multi_viewer.png?raw=true "Multi viewer")

This is much like the viewer for single candidates with a couple of small differences:

 * `next`: Cycle to next plot
 * `previous`: Cycle to previous plot
 
Candidates can also be selected from the list box on the left hand side. The same key bindings exist as above, plus:

 * `next` -- "right" and "down"
 * `previous` -- "left" and "up"


