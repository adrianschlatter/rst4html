Development Notes
+++++++++++++++++

Note so nice
============

:width: attribute of figure
---------------------------

rst4html uses the :width: attribute of a .. figure: to determine how to scale
an image. Unfortunately, the same attribute is also used to give style to the
<img> tag in the generated html. This coupling is unfortunate, as it means that
we cannot define this attribute in CSS (style in the tag directly overrides
anything else).


Often, a fixed rescaling of images to a reasonable size is all
that is needed. This can be done without rst4html, e.g. using ImageMagick. In
such cases, we don't want to use rst4html's scaling. This is possible by simply
not specifying :width: attributes. However, rst4html will still copy the images
to the target directory. This is not very desirable, as it seems easier and
more natural to just instruct ImageMagick to put them in the right place.
