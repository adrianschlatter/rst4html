rst4html
++++++++

The purpose of this tool is to convert restructuredText to html, i.e.,
similar to rst2html provided by docutils. However, rst4html also
provides a number of features not included in docutils, such as variable
substitution and image pre-processing.


==========
variables
==========

{varname} expression will be substituted at conversion time. This intended for images and figures. Example::

	.. figure:: {imp}/DSC_9657.JPG
	    :alt: Wagen- und Zeltburg mit Campingtischen in der Mitte.
	    :width: 60%

	    Wir geniessen den Abend in der "Wagenburg" mit Aussicht auf
	    den See und das Feuerwerk.


This will be converted as follows:

>>> rst4html --subst '{"imp": "../pics/iceland"}' my.rst


================
Image processing
================

A key feature of rst4html is the ability to link to images at arbitrary
places. The tool will collect the images from there, process them, and
store them very you want them to be. This way, your high-resolution
fotos remain in your foto library. You can also apply transformations
to the images, e.g., rescaling to a lower resolution according to
the :width: specification in your .rst document. If :width: is specified
as a percentage, you have to specify the --targetlinewidth (in pixels)
to rst4html (corresponds to 100%).

>>> rst4html --imgtargetdir './imgs' --targetlinewidth 600 my.rst

