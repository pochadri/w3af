'''
helpers.py

Copyright 2012 Andres Riancho

This file is part of w3af, w3af.sourceforge.net .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

'''
import os
import pprint

try:
    from gtk import gtk_version, pygtk_version
except:
    gtk_version = []
    pygtk_version = []

import sys
import tempfile
import StringIO

from core.controllers.misc.get_w3af_version import get_w3af_version
from core.data.fuzzer.fuzzer import createRandAlNum

# String containing the versions for python, gtk and pygtk
VERSIONS = '''
Python version:\n%s\n
GTK version:%s
PyGTK version:%s\n\n
%s
''' % \
    (sys.version,
    ".".join(str(x) for x in gtk_version),
    ".".join(str(x) for x in pygtk_version),
    get_w3af_version())
    
def pprint_plugins( w3af_core ):
    # Return a pretty-printed string from the plugins dicts
    import copy
    from itertools import chain
    plugs_opts = copy.deepcopy(w3af_core.plugins.getAllPluginOptions())
    plugs = w3af_core.plugins.getAllEnabledPlugins()

    for ptype, plist in plugs.iteritems():
        for p in plist:
            if p not in chain(*(pt.keys() for pt in \
                                    plugs_opts.itervalues())):
                plugs_opts[ptype][p] = {}
    
    plugins = StringIO.StringIO()
    pprint.pprint(plugs_opts, plugins)
    return  plugins.getvalue()

def gettempdir():
    return tempfile.gettempdir()

def create_crash_file(exception):
    filename = "w3af_crash-" + createRandAlNum(5) + ".txt"
    filename = os.path.join( gettempdir() , filename ) 
    crash_dump = file(filename, "w")
    crash_dump.write(_('Submit this bug here: https://sourceforge.net/apps/trac/w3af/newticket \n'))
    crash_dump.write(VERSIONS)
    crash_dump.write(exception)
    crash_dump.close()
    return filename
