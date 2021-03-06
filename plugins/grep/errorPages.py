'''
errorPages.py

Copyright 2006 Andres Riancho

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

import core.controllers.outputManager as om
# options
from core.data.options.option import option
from core.data.options.optionList import optionList
from core.data.esmre.multi_in import multi_in
from core.data.esmre.multi_re import multi_re

from core.controllers.basePlugin.baseGrepPlugin import baseGrepPlugin

import core.data.kb.knowledgeBase as kb
import core.data.kb.info as info

import re


class errorPages(baseGrepPlugin):
    '''
    Grep every page for error pages.
      
    @author: Andres Riancho ( andres.riancho@gmail.com )
    '''

    ERROR_PAGES = (
        '<H1>Error page exception</H1>',
        # This signature fires up also in default 404 pages of aspx which generates 
        # a lot of noise, so ... disabling it
        #mesg.append('<span><H1>Server Error in ',
        '<h2> <i>Runtime Error</i> </h2></span>',
        '<h2> <i>Access is denied</i> </h2></span>',
        '<H3>Original Exception: </H3>',
        'Server object error',
        'invalid literal for int()',
        'exceptions.ValueError',
        
        '<font face="Arial" size=2>Type mismatch: ',
        '[an error occurred while processing this directive]',
        
        '<HTML><HEAD><TITLE>Error Occurred While Processing Request</TITLE>'
        '</HEAD><BODY><HR><H3>Error Occurred While Processing Request</H3><P>',
        
        # VBScript
        '<p>Microsoft VBScript runtime </font>',
        "<font face=\"Arial\" size=2>error '800a000d'</font>",

        # nwwcgi errors
        '<TITLE>nwwcgi Error',
        
        # ASP error I found during a pentest, the ASP used a foxpro db, not a SQL injection
        '<font face="Arial" size=2>error \'800a0005\'</font>',
        '<h2> <i>Runtime Error</i> </h2></span>',
        # Some error in ASP when using COM objects.
        'Operation is not allowed when the object is closed.',
        # An error when ASP tries to include something and it fails
        '<p>Active Server Pages</font> <font face="Arial" size=2>error \'ASP 0126\'</font>',
        
        # ASPX
        '<b> Description: </b>An unhandled exception occurred during the execution of the'
        ' current web request',
        
        # Struts
        '] does not contain handler parameter named',
        
        # PHP
        '<b>Warning</b>: ',
        'No row with the given identifier',
        'open_basedir restriction in effect',
        "eval()'d code</b> on line <b>",
        "Cannot execute a blank command in",
        "Fatal error</b>:  preg_replace",
        "thrown in <b>",
        "#0 {main}",
        "Stack trace:",
        "</b> on line <b>",
        
        # python
        "PythonHandler django.core.handlers.modpython",
        "t = loader.get_template(template_name) # You need to create a 404.html template.",
        '<h2>Traceback <span>(innermost last)</span></h2>',
        
        # Java
        '[java.lang.',
        'class java.lang.',
        'java.lang.NullPointerException',
        'java.rmi.ServerException',
        'at java.lang.',
        
        'onclick="toggle(\'full exception chain stacktrace\')"',
        'at org.apache.catalina',
        'at org.apache.coyote.',
        'at org.apache.tomcat.',
        'at org.apache.jasper.',

        # ruby
        '<h1 class="error_title">Ruby on Rails application could not be started</h1>',


        # Coldfusion
        '<title>Error Occurred While Processing Request</title></head><body><p></p>',
        '<HTML><HEAD><TITLE>Error Occurred While Processing Request</TITLE></HEAD><BODY><HR><H3>',
        '<TR><TD><H4>Error Diagnostic Information</H4><P><P>',
        
        '<li>Search the <a href="http://www.macromedia.com/support/coldfusion/" '
        'target="new">Knowledge Base</a> to find a solution to your problem.</li>',
        
        # http://www.programacion.net/asp/articulo/kbr_execute/
        'Server.Execute Error',
        
        # IIS
        '<h2 style="font:8pt/11pt verdana; color:000000">HTTP 403.6 - Forbidden: IP address rejected<br>',
        '<TITLE>500 Internal Server Error</TITLE>',
    )
    _multi_in = multi_in( ERROR_PAGES )

    
    VERSION_REGEX = (
        ('<address>(.*?)</address>', 'Apache'),
        ('<HR size="1" noshade="noshade"><h3>(.*?)</h3></body>', 'Apache Tomcat'),
        ('<a href="http://www.microsoft.com/ContentRedirect.asp\?prd=iis&sbp=&pver=(.*?)&pid=&ID', 'IIS' ),
        
        # <b>Version Information:</b>&nbsp;Microsoft .NET Framework Version:1.1.4322.2300; ASP.NET Version:1.1.4322.2300
        ('<b>Version Information:</b>&nbsp;(.*?)\n', 'ASP .NET')    
    )
    _multi_re = multi_re( VERSION_REGEX )

    
    def __init__(self):
        baseGrepPlugin.__init__(self)
        
        self._already_reported_versions = []
        self._compiled_regex = []
        
    def grep(self, request, response):
        '''
        Plugin entry point, find the error pages and report them.
        
        @parameter request: The HTTP request object.
        @parameter response: The HTTP response object
        @return: None
        '''
        if response.is_text_or_html():
            
            for msg in self._multi_in.query( response.body ):
                i = info.info()
                i.setPluginName(self.getName())
                
                # Set a nicer name for the vulnerability
                name = 'Descriptive error page - "'
                if len(msg) > 12:
                    name += msg[:12] + '..."'
                else:
                    name += msg + '"'
                i.setName( name )
                
                i.setURL( response.getURL() )
                i.setId( response.id )
                i.setDesc( 'The URL: "' + response.getURL() + '" contains the descriptive error: "' + msg + '"' )
                i.addToHighlight( msg ) 
                kb.kb.append( self , 'errorPage' , i )
                
                # There is no need to report more than one info for the same result,
                # the user will read the info object and analyze it even if we report it
                # only once. If we report it twice, he'll get mad ;)
                break
                    
            # Now i'll check if I can get a version number from the error page
            # This is common in apache, tomcat, etc...
            if response.getCode() in range(400, 600):
                
                for match, regex_str, regex_comp, server in self._multi_re.query( response.body ):
                    match_string = match.group(0)
                    if match_string not in self._already_reported_versions:
                        # Save the info obj
                        i = info.info()
                        i.setPluginName(self.getName())
                        i.setName('Error page with information disclosure')
                        i.setURL( response.getURL() )
                        i.setId( response.id )
                        i.setName( 'Error page with information disclosure' )
                        i.setDesc( 'An error page sent this ' + server +' version: "' + match_string + '".'  )
                        i.addToHighlight( server )
                        i.addToHighlight( match_string )
                        kb.kb.append( self , 'server' , i )
                        # Save the string
                        kb.kb.append( self , 'server' , match_string )
                        self._already_reported_versions.append( match_string )
        
    def setOptions( self, OptionList ):
        pass
    
    def getOptions( self ):
        '''
        @return: A list of option objects for this plugin.
        '''    
        ol = optionList()
        return ol

    def end(self):
        '''
        This method is called when the plugin wont be used anymore.
        '''
        self.printUniq( kb.kb.getData( 'errorPages', 'errorPage' ), 'URL' )

    def getPluginDeps( self ):
        '''
        @return: A list with the names of the plugins that should be run before the
        current one.
        '''
        return []
    
    def getLongDesc( self ):
        '''
        @return: A DETAILED description of the plugin functions and features.
        '''
        return '''
        This plugin scans every page for error pages, and if possible extracts the web server
        or programming framework information.
        '''
