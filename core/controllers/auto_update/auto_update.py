'''
auto_update.py

Copyright 2011 Andres Riancho

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
from datetime import datetime, date, timedelta
import os
import ConfigParser
import threading


def exit_on_keyboard_interrupt(func):
    '''
    This decorator can be used to catch Keyboard interruption signals
    and terminate the program successfuly.
    '''
    def new_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            import sys
            sys.exit(0)
    new_func.__name__ = func.__name__
    new_func.__doc__ = func.__doc__
    new_func.__dict__.update(func.__dict__)
    return new_func


class SVNError(Exception):
    pass


class SVNUpdateError(SVNError):
    pass


class SVNCommitError():
    pass


class SVNClient(object):
    '''
    Typically an abstract class. Intended to define behaviour. Not to be
    instantiated.
    '''

    def __init__(self, localpath):
        self._localpath = localpath
        self._repourl = self._get_repourl()
        # Action Locker! 
        self._actionlock = threading.RLock()

    def _get_repourl(self):
        '''
        Get repo's URL. To be implemented by subclasses.
        '''
        raise NotImplementedError

    def update(self):
        '''
        TODO: Add docstring.
        '''
        raise NotImplementedError

    def commit(self):
        '''
        TODO: Add docstring.
        '''
        raise NotImplementedError

    def status(self, path=None):
        '''
        TODO: Add docstring.
        '''
        raise NotImplementedError

    def list(self, path_or_url=None):
        '''
        TODO: Add docstring.
        '''
        raise NotImplementedError

    def diff(self, localpath, rev=None):
        '''
        TODO: Add docstring.
        '''
        raise NotImplementedError



import pysvn

# Actions on files
FILE_UPD = 'UPD' # Updated
FILE_NEW = 'NEW' # New
FILE_DEL = 'DEL' # Removed

wcna = pysvn.wc_notify_action
pysvn_action_translator = {
    wcna.update_add: FILE_NEW,
    wcna.update_delete: FILE_DEL,
    wcna.update_update: FILE_UPD
}

# Files statuses
ST_CONFLICT = 'C'
ST_NORMAL = 'N'
ST_UNVERSIONED = 'U'
ST_MODIFIED = 'M'
ST_UNKNOWN = '?'

wcsk = pysvn.wc_status_kind
pysvn_status_translator = {
    wcsk.conflicted: ST_CONFLICT,
    wcsk.normal: ST_NORMAL,
    wcsk.unversioned: ST_UNVERSIONED,
    wcsk.modified: ST_MODIFIED
}


class W3afSVNClient(SVNClient):
    '''
    TODO: Add docstring
    '''

    UPD_ACTIONS = (wcna.update_add, wcna.update_delete, wcna.update_update)

    def __init__(self, localpath):
        '''
        TODO: Add docstring
        '''
        self._svnclient = pysvn.Client()
        # Call parent's __init__
        super(W3afSVNClient, self).__init__(localpath)
        # Set callback function
        self._svnclient.callback_notify = self._register
        # Events occurred in current action
        self._events = []

    @property
    def URL(self):
        return self._repourl

    def update(self):
        '''
        TODO: Add docstring
        '''
        with self._actionlock:
            self._events = []
            try:
                pysvn_rev = self._svnclient.update(self._localpath)[0]
            except pysvn.ClientError, ce:
                raise SVNUpdateError(*ce.args)
            else:
                updfiles = self._filter_files(self.UPD_ACTIONS)
                updfiles.rev = Revision(pysvn_rev.number, pysvn_rev.date)
                return updfiles

    def commit(self):
        '''
        TODO: Add docstring
        '''
        pass

    def status(self, localpath=None):
        '''
        TODO: Add docstring
        
        @param localpath: Path to get the status from. If is None use project
            root.
        '''
        with self._actionlock:
            path = localpath or self._localpath
            try:
                entries = self._svnclient.status(path, recurse=False)
            except pysvn.ClientError, ce:
                raise SVNError(*ce)
            else:
                res = [(ent.path, pysvn_status_translator.get(ent.text_status,
                                              ST_UNKNOWN)) for ent in entries]
                return SVNFilesList(res)

    def list(self, path_or_url=None):

        with self._actionlock:
            if not path_or_url:
                path_or_url = self._localpath
            try:
                entries = self._svnclient.list(path_or_url, recurse=False)
            except pysvn.ClientError, ce:
                raise SVNError(*ce)
            else:
                res = [(ent.path, None) for ent, _ in entries]
                return SVNFilesList(res)

    def diff(self, localpath, rev=None):

        with self._actionlock:
            path = os.path.join(self._localpath, localpath)
            # If no rev is passed the compare to HEAD
            if rev is None:
                rev = pysvn.Revision(pysvn.opt_revision_kind.head)
            tempfile = os.tempnam()
            diff_str = self._svnclient.diff(tempfile, path, revision1=rev)
            return diff_str

    def log(self, start_rev, end_rev):
        '''
        Return SVNLogList of log messages between `start_rev`  and `end_rev`
        revisions.
        
        @param start_rev: Revision object
        @param end_rev: Revision object
        '''
        with self._actionlock:
            # Expected by pysvn.Client.log method
            pysvnstartrev = pysvn.Revision(pysvn.opt_revision_kind.number, 
                               start_rev.number)
            pysvnendrev = pysvn.Revision(pysvn.opt_revision_kind.number,
                                         end_rev.number)
            logs = (l.message for l in self._svnclient.log(
                                                self._localpath,
                                                revision_start=pysvnstartrev,
                                                revision_end=pysvnendrev))
            rev = end_rev if (end_rev.number > start_rev.number) else start_rev
            return SVNLogList(logs, rev)


    def _get_repourl(self):
        '''
        Get repo's URL.
        '''
        svninfo = self._get_svn_info(self._localpath)
        return svninfo.URL

    def _get_svn_info(self, path_or_url):
        try:
            return self._svnclient.info2(path_or_url, recurse=False)[0][1]
        except pysvn.ClientError, ce:
            raise SVNUpdateError(*ce.args)

    def get_revision(self, local=True):
        '''
        Return Revision object.
        
        @param local: If true return local's revision data; otherwise use
        repo's.
        '''
        path_or_url = self._localpath if local else self._repourl
        _rev = self._get_svn_info(path_or_url).rev
        return Revision(_rev.number, _rev.date)

    def _filter_files(self, filterbyactions=()):
        '''
        Filter... Return files-actions
        @param filterby: 
        '''
        files = SVNFilesList()
        for ev in self._events:
            action = ev['action']
            if action in filterbyactions:
                path = ev['path']
                # We're not interested on reporting directories unless a 
                # 'delete' has been performed on them
                if not os.path.isdir(path) or action == wcna.update_delete:
                    files.append(path, pysvn_action_translator[action])
        return files

    def _register(self, event):
        '''
        Callback method. Registers all events taking place during this action.
        '''
        self._events.append(event)


class Revision(object):
    '''
    Our own class for revisions.
    '''

    def __init__(self, number, date):
        self._number = number
        self._date = date

    def __eq__(self, rev):
        return self._number == rev.number and \
                self._date == rev.date

    def __lt__(self, rev):
        return self._number < rev.number

    @property
    def date(self):
        return self._date

    @property
    def number(self):
        return self._number


# Limit of lines to SVNList types. To be used in __str__ method re-definition.
PRINT_LINES = 20

class SVNList(list):

    '''
    Wrapper for python list type. It may contain the number of the current
    revision and do a custom list print. Child classes are encourage to 
    redefine the __str__ method.
    '''

    def __init__(self, seq=(), rev=None):
        '''
        @param rev: Revision object
        '''
        list.__init__(self, seq)
        self._rev = rev
        self._sorted = True

    def _getrev(self):
        return self._rev

    def _setrev(self, rev):
        self._rev = rev

    # TODO: Cannot use *full* decorators as we're still on py2.5
    rev = property(_getrev, _setrev)

    def __eq__(self, olist):
        return list.__eq__(self, olist) and self._rev == olist.rev


class SVNFilesList(SVNList):
    '''
    Custom SVN files list holder.
    '''

    def __init__(self, seq=(), rev=None):
        SVNList.__init__(self, seq, rev)
        self._sorted = True

    def append(self, path, status):
        list.append(self, (path, status))
        self._sorted = False

    def __str__(self):
        # First sort by status
        sortfunc = lambda x, y: cmp(x[1], y[1])
        self.sort(cmp=sortfunc)
        lines, rest = self[:PRINT_LINES], max(len(self) - PRINT_LINES, 0)
        print_list = ['%s %s' % (f, s) for s, f in lines]
        if rest:
            print_list.append('and %d files more.' % rest)
        if self._rev:
            print_list.append('At revision %s.' % self._rev.number)
        return os.linesep.join(print_list)


class SVNLogList(SVNList):
    '''
    Provides a custom way to print a SVN logs list.
    '''
    def __str__(self):
        print_list = []
        if self._rev:
            print_list.append('Revision %s:' % self._rev.number)
        lines, rest = self[:PRINT_LINES], max(len(self) - PRINT_LINES, 0)
        print_list += ['%3d. %s' % (n + 1, ln) for n, ln in enumerate(lines)]
        if rest:
            print_list.append('and %d commit logs more.' % rest)
        return os.linesep.join(print_list)


# Use this class to perform svn actions on code
SVNClientClass = W3afSVNClient


# Facade class. Intended to be used to to interact with the module
class VersionMgr(object): #TODO: Make it singleton?

    # Events constants
    ON_UPDATE = 1
    ON_CONFIRM_UPDATE = 2
    ON_UPDATE_CHECK = 3
    ON_COMMIT = 4

    def __init__(self, localpath, log):
        '''
        W3af version manager class. Handles the logic concerning the 
        automatic update/commit process of the code.
        
        @param localpath: Working directory
        @param log: Default output function
        '''
        self._localpath = localpath

        self._log = log
        self._client = SVNClientClass(localpath)
        # Registered functions
        self._reg_funcs = {}
        # Startup configuration
        self._start_cfg = StartUpConfig()

    def is_update_avail(self):
        self._notify(VersionMgr.ON_UPDATE_CHECK)
        return self._client.need_to_update()

    @exit_on_keyboard_interrupt
    def update(self, askvalue=None, print_result=False, show_log=False):
        '''
        Perform code update if necessary.
        
        @param askvalue: Callback function that will output the update 
            confirmation response.
        @param print_result: If True print the result files using instance's
            log function.
        @param show_log: If True interact with the user through `askvalue` and
            show a summary of the log messages.
        '''
        client = self._client
        lrev = client.get_revision(local=True)
        files = SVNFilesList(rev=lrev)

        if self._has_to_update():
            self._notify(VersionMgr.ON_UPDATE)
            rrev = client.get_revision(local=False)

            # If local rev is not lt repo's then we got nothing to update.
            if not (lrev < rrev):
                return files

            proceed_upd = True
            # Call callback function
            if askvalue:
                proceed_upd = askvalue(\
                'Your current w3af installation is r%s. Do you want to ' \
                'update to r%s [y/N]? ' % (lrev.number, rrev.number))
                proceed_upd = (proceed_upd.lower() == 'y')

            if proceed_upd:
                msg = 'w3af is updating from the official SVN server...'
                self._notify(VersionMgr.ON_UPDATE, msg)
                # Find new deps.
                newdeps = self._added_new_dependencies()
                if newdeps:
                    msg = 'At least one new dependency (%s) was included in ' \
                    'w3af. Please update manually.' % str(', '.join(newdeps))
                    self._notify(VersionMgr.ON_UPDATE, msg)
                else:
                    # Finally do the update!
                    files = client.update()
                    # Now save today as last-update date and persist it.
                    self._start_cfg.last_upd = date.today()
                    self._start_cfg.save()

            # Before returning perform some interaction with the user if
            # requested.
            if print_result:
                self._log(str(files))
    
            if show_log:
                show_log = askvalue('Do you want to see a summary of the ' \
                'new code commits log messages? [y/N]? ').lower() == 'y'
                if show_log:
                    self._log(str(self._client.log(lrev, rrev)))
        return files

    def status(self, path=None):
        return self._client.status(path)

    def commit(self):
        #self._notify(VersionMgr.ON_COMMIT)
        pass

    def register(self, eventname, func, msg):
        funcs = self._reg_funcs.setdefault(eventname, [])
        funcs.append((func, msg))

    def _notify(self, event, msg=None):
        '''
        Call registered functions for event. If `msg` is not None then force
        to call the registered functions with `msg`.
        '''
        for f, _msg in self._reg_funcs.get(event, []):
            f(msg or _msg)

    def _added_new_dependencies(self):
        '''
        Return tuple with the dependencies added to extlib/ in the repo if
        any. Basically it compares local dirs under extlib/ to those in the
        repo as well as checks if at least a new sentence containing the 
        import keyword was added to the dependencyCheck.py file.
        '''
        #
        # Check if a new directory was added to repo's extlib
        #
        client = self._client
        ospath = os.path
        join = ospath.join
        # Find dirs in repo
        repourl = self._client.URL + '/' + 'extlib'
        # In repo we distinguish dirs from files by the dot (.) presence
        repodirs = (ospath.basename(d) for d, _ in client.list(repourl)[1:] \
                                        if ospath.basename(d).find('.') == -1)
        # Get local dirs
        extliblocaldir = join(self._localpath, 'extlib')
        extlibcontent = (join(extliblocaldir, f) for f in \
                                                os.listdir(extliblocaldir))
        localdirs = (ospath.basename(d) for d in extlibcontent \
                                                        if ospath.isdir(d))
        # New dependencies
        deps = tuple(set(repodirs).difference(localdirs))

        #
        # Additional constraint: We should verify that at least an import
        # sentence was added to the dependencyCheck.py file
        #
        if deps:
            depcheck_fpath = 'core/controllers/misc/dependencyCheck.py'
            diff_str = client.diff(depcheck_fpath)
            # SVN shows HEAD rev's new lines preceeded by a '-' char.
            newlineswithimport = \
                [nl for nl in diff_str.split('\n') \
                        if nl.startswith('-') and nl.find('import') != -1]
            # Ok, no import sentence was detected so no dep. was *really*
            # added.
            if not newlineswithimport:
                deps = ()

        return deps
    
    def _has_to_update(self):
        '''
        Helper method that figures out if an update should be performed
        according to the startup cfg file.
        Some rules:
            1) IF auto_upd is False THEN return False
            2) IF last_upd == 'yesterday' and freq == 'D' THEN return True
            3) IF last_upd == 'two_days_ago' and freq == 'W' THEN return False.
        @return: Boolean value.
        '''
        startcfg = self._start_cfg
        # That's it!
        if not startcfg.auto_upd:
            return False
        else:        
            freq = startcfg.freq
            diff_days = max((date.today()-startcfg.last_upd).days, 0)
            
            if (freq == StartUpConfig.FREQ_DAILY and diff_days > 0) or \
                (freq == StartUpConfig.FREQ_WEEKLY and diff_days > 6) or \
                (freq == StartUpConfig.FREQ_MONTHLY and diff_days > 29):
                return True
            return False


from core.controllers.misc.homeDir import get_home_dir

class StartUpConfig(object):
    '''
    Wrapper class for ConfigParser.ConfigParser.
    Holds the configuration for the VersionMgr update/commit process
    '''

    ISO_DATE_FMT = '%Y-%m-%d'
    # Frequency constants
    FREQ_DAILY = 'D' # [D]aily
    FREQ_WEEKLY = 'W' # [W]eekly
    FREQ_MONTHLY = 'M' # [M]onthly

    def __init__(self):
        
        self._start_cfg_file = os.path.join(get_home_dir(), 'startup.conf')
        self._start_section = 'StartConfig'
        defaults = {'auto-update': 'true', 'frequency': 'D', 
                    'last-update': 'None'}
        self._config = ConfigParser.ConfigParser(defaults)
        self._autoupd, self._freq, self._lastupd = self._load_cfg()

    ### PROPERTIES #

    def _get_last_upd(self):
        '''
        Getter method.
        '''
        return self._lastupd

    def _set_last_upd(self, datevalue):
        '''
        @param datevalue: datetime.date value
        '''
        self._lastupd = datevalue
        self._config.set(self._start_section, 'last-update', datevalue.isoformat())

    # TODO: Cannot use *full* decorators as we're still on py2.5
    # Read/Write property
    last_upd = property(_get_last_upd, _set_last_upd)

    @property
    def freq(self):
        return self._freq

    @property
    def auto_upd(self):
        return self._autoupd

    ### METHODS #

    def _load_cfg(self):
        '''
        Loads configuration from config file.
        '''
        config = self._config
        startsection = self._start_section
        if not config.has_section(startsection):
            config.add_section(startsection)

        # Read from file
        config.read(self._start_cfg_file)

        auto_upd = config.get(startsection, 'auto-update', raw=True)
        boolvals = {'false': 0, 'off': 0, 'no': 0,
                    'true': 1, 'on': 1, 'yes': 1}
        auto_upd = bool(boolvals.get(auto_upd.lower(), False))

        freq = config.get(startsection, 'frequency', raw=True).upper()
        if freq not in (StartUpConfig.FREQ_DAILY, StartUpConfig.FREQ_WEEKLY,
                        StartUpConfig.FREQ_MONTHLY):
            freq = StartUpConfig.FREQ_DAILY

        lastupdstr = config.get(startsection, 'last-update', raw=True).upper()
        # Try to parse it
        try:
            lastupd = datetime.strptime(lastupdstr, self.ISO_DATE_FMT).date()
        except:
            # Provide default value that enforces the update to happen
            lastupd = date.today() - timedelta(days=31)
        return (auto_upd, freq, lastupd)

    def save(self):
        '''
        Saves current values to cfg file
        '''
        with open(self._start_cfg_file, 'wb') as configfile:
            self._config.write(configfile)
