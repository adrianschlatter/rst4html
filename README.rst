Travel-Diary Generator
+++++++++++++++++++++++

The purpose of this tool is to convert a travel diary ReST document to html format.

A travel diary uses the following features not provided by docutils:

========
Features
========


variables
==========

{varname} expression will be substituted at conversion time. This intended for images and figures. Example::


.. figure:: {imp}/DSC_9657.JPG
    :alt: Wagen- und Zeltburg mit Campingtischen in der Mitte.
    :width: 60%

    Wir geniessen den Abend in der "Wagenburg" mit Aussicht auf
    den See und das Feuerwerk.


This will be converted as follows:

>>> traveldiary2html imp='../../images/icelandtravel' my.rst


Image processing
================

A key feature of traveldiary2html is the ability to link to images at arbitrary places. The tool will collect the images from there, process them, and store them very you want them to be. This way, your high-resolution fotos remain in your fotolibrary. Your travel diary links to those images directly or to a transformed copy that is automatically placed where you need it. The transformation may be, e.g., a rescaling to a lower resolution according to the :width: specification in your .rst document. Furthermore, the images will be clickable and will link to a high(er) resolution image that will open in a lightbox.


==============
Implementation
==============

docutils processes a document in the following steps:

	- reader
	- parser
	- transforms
	- writer

Variables are implemented in a custom reader: It reads the ReST document with variables and applies python's .format() routine. The arguments to .format() (i.e. the variable substitutions) are taken from the command line.

Image rescaling and collection are implemented in custom transforms. The transforms apply to image and figure directives. The image is loaded from the URL argument. It is transformed according to the options given to the directive. Then, the image is stored in the new location (defined as command line argument) and the directives URL argument is modified to indicate the new location.

Optionally (command-line argument), traveldiary2html will store an additional, larger version of the image, which will open upon clicking the smaller image.










