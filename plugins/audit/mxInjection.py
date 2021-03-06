'''
mxInjection.py

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
from __future__ import with_statement

import core.controllers.outputManager as om

# options
from core.data.options.option import option
from core.data.options.optionList import optionList

from core.controllers.basePlugin.baseAuditPlugin import baseAuditPlugin
from core.controllers.w3afException import w3afException
from core.data.fuzzer.fuzzer import createMutants
from core.data.esmre.multi_in import multi_in

import core.data.kb.knowledgeBase as kb
import core.data.kb.vuln as vuln
import core.data.constants.severity as severity


class mxInjection(baseAuditPlugin):
    '''
    Find MX injection vulnerabilities.
    @author: Andres Riancho ( andres.riancho@gmail.com )
    '''

    MX_ERRORS = (
        'Unexpected extra arguments to Select',
        'Bad or malformed request',
        'Could not access the following folders',
        'A000',
        'A001',
        'Invalid mailbox name',
        'To check for outside changes to the folder list go to the folders page'
    )
    _multi_in = multi_in( MX_ERRORS )

    def __init__(self):
        '''
        Plugin added just for completeness... I dont really expect to find one of this bugs
        in my life... but well.... if someone , somewhere in the planet ever finds a bug of using
        this plugin... THEN my job has been done :P
        '''
        baseAuditPlugin.__init__(self)
        
        # Internal variables.
        self._errors = []

    def audit(self, freq ):
        '''
        Tests an URL for mx injection vulnerabilities.
        
        @param freq: A fuzzableRequest
        '''
        om.out.debug( 'mxInjection plugin is testing: ' + freq.getURL() )
        
        oResponse = self._uri_opener.send_mutant(freq)
        mx_injection_strings = self._get_MX_injection_strings()
        mutants = createMutants( freq , mx_injection_strings, oResponse=oResponse )
            
        for mutant in mutants:
            
            # Only spawn a thread if the mutant has a modified variable
            # that has no reported bugs in the kb
            if self._has_no_bug(mutant):
                args = (mutant,)
                kwds = {'callback': self._analyze_result }
                self._run_async(meth=self._uri_opener.send_mutant, args=args,
                                                                    kwds=kwds)
        self._join()
        
            
    def _analyze_result( self, mutant, response ):
        '''
        Analyze results of the _send_mutant method.
        '''
        with self._plugin_lock:
            
            # I will only report the vulnerability once.
            if self._has_no_bug(mutant):
                
                mx_error_list = self._multi_in.query( response.body )
                for mx_error in mx_error_list:
                    if mx_error not in mutant.getOriginalResponseBody():
                        v = vuln.vuln( mutant )
                        v.setPluginName(self.getName())
                        v.setName( 'MX injection vulnerability' )
                        v.setSeverity(severity.MEDIUM)
                        v.setDesc( 'MX injection was found at: ' + mutant.foundAt() )
                        v.setId( response.id )
                        v.addToHighlight( mx_error )
                        kb.kb.append( self, 'mxInjection', v )
                        break
    
    def end(self):
        '''
        This method is called when the plugin wont be used anymore.
        '''
        self._join()
        self.printUniq( kb.kb.getData( 'mxInjection', 'mxInjection' ), 'VAR' )
    
    def _get_MX_injection_strings( self ):
        '''
        Gets a list of strings to test against the web app.
        
        @return: A list with all mxInjection strings to test. Example: [ '\"','f00000']
        '''
        mx_injection_strings = []
        mx_injection_strings.append('"')
        mx_injection_strings.append('iDontExist')
        mx_injection_strings.append('')
        return mx_injection_strings
        
    def getOptions( self ):
        '''
        @return: A list of option objects for this plugin.
        '''    
        ol = optionList()
        return ol

    def setOptions( self, OptionList ):
        '''
        This method sets all the options that are configured using the user interface 
        generated by the framework using the result of getOptions().
        
        @parameter OptionList: A dictionary with the options for the plugin.
        @return: No value is returned.
        ''' 
        pass

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
        This plugin will find MX injections. This kind of web application errors are mostly seen in
        webmail software. The tests are simple, for every injectable parameter a string with 
        special meaning in the mail server is sent, and if in the response I find a mail server error,
        a vulnerability was found.
        '''
