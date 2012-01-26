#!/usr/bin/env python

#############################################################################
#  contagd - CONvert and TAGging Daemon                                     #
#                                                                           #
#  Copyright (c) 2010 Sebastian Meyer <s.meyer@drachenjaeger.eu>            #
#                                                                           #
#  contagd is free software; you can redistribute it and/or modify it       #
#  under the terms of the GNU General Public License                        #
#  as published by the Free Software Foundation;                            #
#  either version 3 of the License, or (at your option) any later version.  #
#  contagd is distributed in the hope that it will be useful, but           #
#  WITHOUT ANY WARRANTY; without even the implied warranty of               #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                     #
#  See the GNU General Public License for more details.                     #
#                                                                           #
#  You should have received a copy of the GNU General Public License        #
#  along with this program; if not, see <http://www.gnu.org/licenses/>.     #
#############################################################################

import os
import pyinotify
import subprocess
import sys
import traceback
import logging

from contagdlib import tagtool
from contagdlib.daemon import Daemon



class ContagDaemon(Daemon):

    def __init__(self, pidfile, wdir, stdin='/dev/null', stdout='/dev/null',
                 stderr='/dev/null'):
        Daemon.__init__(self, pidfile, stdin, stdout, stderr)
        self.wdir = wdir

    def run(self):
        logging.info("Contagd  started...")
        logging.info("Now watching: %s" % self.wdir)
        wm = pyinotify.WatchManager()
        mask = pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE  # watched events
        # We use these 2 events, because:
        #  CREATE will be thrown when a _new_ file is created
        #  CLOSE_WRITE will be thrown when closing a file opened to write
        #              only read-access will throw CLOSE_NOWRITE
        handler = EventHandler()
        notifier = pyinotify.Notifier(wm, handler)
        wm.add_watch(self.wdir, mask, rec=True)
                    #(directory,events,recursive?)
        notifier.loop()


class EventHandler(pyinotify.ProcessEvent):
    """ This class is a container for the called functions on a event
    """

    def __init__(self):
        """ Init the class-variables """
        self.created_files = []  # for the files which are created

    def process_IN_CREATE(self, event):
        """ this funciton will be called when a new file was created """
        if event.pathname.endswith('.mp3'):
            logging.info("Found a MP3-File created: %s" % (event.pathname))
            self.created_files.append(event.pathname)

    def process_IN_CLOSE_WRITE(self, event):
        """ this function will be called when a file opened for writing
            was closed """
        try:
            if event.pathname in self.created_files:
                logging.info("File closed after write: %s" % (event.pathname))
                self.created_files.remove(event.pathname)
                sourcemp3 = event.pathname
                targetogg = sourcemp3.replace('.mp3', '.ogg')
                ret = self.convert_mp3_to_ogg(sourcemp3, targetogg)
                if ret == 0:
                    try:
                        tagtool.transfer_tags_of_file(sourcemp3, sourcemp3)
                        #This will transfer tags from mp3 to mp3 =>
                        #Any missing tags are added to it
                        tagtool.transfer_tags_of_file(sourcemp3, targetogg)
                    except TypeError:
                        logging.error('Failed to transfer tags: %s => %s'
                                         % (sourcemp3, targetogg))
        except Exception, e:
            msg = "There was a unhandled Exception!\n" \
            "This would kill the daemon, please take a look: %s" % \
            (traceback.format_exc())
            logging.error(msg)

    def convert_mp3_to_ogg(self, sourcemp3, targetogg):
        soxcommand = 'sox %s --comment "" %s' % (sourcemp3, targetogg)
        logging.info("Running SOX: %s" % soxcommand)
        ret = subprocess.call(soxcommand, shell=True)
        # ret = os.waitpid(p.pid, 0)
        if ret == 0:
            logging.info('Convert OK: %s => %s' % (sourcemp3, targetogg))
        else:
            logging.error('Convert ERROR: %s => %s -- SOX Returned: %s'
                  % (sourcemp3, targetogg, str(ret)))
        return ret

if __name__ == "__main__":
    # Checking the command-line-arguments
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-p", "--pidfile", metavar="FILE",
              help="write pid to FILE", dest="pidfile", default="/var/run/contagd.pid")
    parser.add_option("-l", "--logfile", metavar="FILE",
              help="write log to FILE", dest="logfile", default="/var/log/contagd.log")
    parser.add_option("-w", "--watchdir", metavar="DIR",
              help="watch directory DIR for changes", dest="wdir", default="/tmp")
    parser.add_option("-a", "--action", default="start",
              help="action mode: start, stop, restart [default: %default]",
              dest="action")
    (options, args) = parser.parse_args()

    if options.logfile[0] != '/':
        raise ValueError("%s is not an absolute path" % str(options.logfile))
    if options.pidfile[0] != '/':
        raise ValueError("%s is not an absolute path" % str(options.pidfile))
    if options.wdir[0] != '/':
        raise ValueError("%s is not an absolute path" % str(options.wdir))

    daemon = ContagDaemon(options.pidfile,
                          wdir=options.wdir)
    logging.basicConfig(level=logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s:%(module)s %(message)s')
    handler = logging.FileHandler(options.logfile)
    handler.setFormatter(formatter)
    logging.getLogger('').addHandler(handler)
    if 'start' == options.action:
        print "Contagd logging: %s" % (options.logfile)
        daemon.start()
    elif 'stop' == options.action:
        daemon.stop()
    elif 'restart' == options.action:
        daemon.restart()
    sys.exit(0)
