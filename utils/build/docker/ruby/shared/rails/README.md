# Shared Rails code

This directory contains code to be shared between the various Rails
applications.

The files in this directory should be arranged using the normal Rails
conventions, e.g. app/models/foo.rb, app/controllers/bar_controller.rb, etc.

When docker images are built, files in this directory are copied over
the base Rails applications.
