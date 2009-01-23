#!/usr/bin/python
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# $Id$
#

#####################################################################
###    WORK IN PROGRESS -- WORK IN PROGRESS -- WORK IN PROGRESS   ###
#####################################################################

# TODO
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# - Determine how to create hard links
# - Write directory tree constructor to replicate source
# - Copy files from source
#   - Copy bytes
#   - Set owner/group
#   - Set permissions
#   - Set accessed/modified times (utime() function)
# - Allow resuming a copy of a directory tree
#   - Only copy what hasn't been done already
#   - Check for incomplete copies
# - Recover from errors
#   - Attempt the operation 3 times before treating as an error
#   - Keep going despite errors
import os
import sys
from stat import *

class TreeVisitor:
    """Visitor pattern for walktree function. As tree is traversed,
    methods of the visitor are invoked."""

    def dir(self, dir):
        """A directory has been encountered."""
        pass

    def file(self, file):
        """A file has been encountered."""
        pass

    def link(self, link):
        """A symbolic link has been encountered."""
        pass

def walktree(dir, visitor):
    """Recursively descend the directory tree rooted at dir,
       calling the visitor for each entry encountered. The tree
       is traversed in depth-first order, which is most space
       efficient and lends itself well to directory operations."""

    for entry in os.listdir(dir):
        pathname = os.path.join(dir, entry)
        try:
            mode = os.lstat(pathname)[ST_MODE]
            if S_ISDIR(mode):
                visitor.dir(pathname)
            elif S_ISLNK(mode):
                visitor.link(pathname)
            elif S_ISREG(mode):
                visitor.file(pathname)
            else:
                print 'Unknown file %s' % pathname
        except OSError:
            print 'Error reading %s' % pathname

class BasicTreeVisitor(TreeVisitor):
    def dir(self, dir):
        walktree(dir, self)

    def file(self, file):
        print file

    def link(self, link):
        print '%s@' % link

if __name__ == '__main__':
    print 'THIS IS A WORK IN PROGRESS, DO NOT EXPECT IT TO WORK!'
    if len(sys.argv) != 2:
        print 'Usage: timecopy.py <path>'
    else:
        walktree(sys.argv[1], BasicTreeVisitor())
