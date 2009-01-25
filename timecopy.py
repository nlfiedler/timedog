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
#XXX   WORK IN PROGRESS -- WORK IN PROGRESS -- WORK IN PROGRESS   ###
#####################################################################
#
# TODO EVENTUALLY
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# - Implement verbose mode
# - Implement dry-run mode
# - Allow resuming a copy of a directory tree
#   - Check for incomplete copies
#   - Only copy what hasn't been done already
# - Recover from errors
#   - Attempt the operation 3 times before treating as an error
#   - Keep going despite errors
# - Detect presence of multiple hosts in backup, prompt user for
#   which ones to backup (allow backing up all)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
import getopt
import os
import re
import shutil
import sys
from stat import *

class TreeVisitor:
    """Visitor pattern for visitfiles function. As tree is traversed,
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

def visitfiles(dir, visitor):
    "Calls the visitor for each entry encountered in the directory."

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

class CopyInitialVisitor(TreeVisitor):
    """Copies a directory tree from one place to another."""

    def copytree(self, src, dst):
        """Copies the directory tree rooted at src to dst."""
        self.src = src
        self.dst = dst
        visitfiles(src, self)

    def dir(self, dir):
        # Create destination directory, copying stats and ownership.
        dst = re.sub(self.src, self.dst, dir)
        os.mkdir(dst)
        shutil.copystat(dir, dst)
        stats = os.lstat(dir)
        os.lchown(dst, stats[ST_UID], stats[ST_GID])
        # Continue traversal...
        visitfiles(dir, self)

    def file(self, file):
        dst = re.sub(self.src, self.dst, file)
        # Copy file contents from snapshot to destination.
        shutil.copyfile(file, dst)
        # Copy the permissions and accessed/modified times.
        shutil.copystat(file, dst)
        # Copy the owner/group values to destination.
        stats = os.lstat(file)
        os.lchown(dst, stats[ST_UID], stats[ST_GID])

    def link(self, link):
        # Copy link to destination.
        lnk = os.readlink(link)
        dst = re.sub(self.src, self.dst, link)
        os.symlink(lnk, dst)
        stats = os.lstat(link)
        os.lchown(dst, stats[ST_UID], stats[ST_GID])

class CopyBackupVisitor(TreeVisitor):
    """Copies a directory tree and its files, where those entries differ
       from a reference tree. That is, if any entry has the same inode
       value as the corresponding entry in the reference tree, a new
       hard link is made in the destination, and nothing further is
       done with that entry (directories are not traversed, files are
       not copied)."""

    def __init__(self, old):
        "old is the reference tree to which src will be compared"
        self.old = old

    def copytree(self, src, dst):
        "Copy the tree rooted at src to dst"
        self.src = src
        self.dst = dst
        visitfiles(src, self)

    def dir(self, dir):
        stats = os.lstat(dir)
        old = re.sub(self.src, self.old, dir)
        ostats = os.lstat(old)
        dst = re.sub(self.src, self.dst, dir)
        if stats[ST_INO] != ostats[ST_INO]:
            # Create destination directory, copying stats and ownership.
            os.mkdir(dst)
            shutil.copystat(dir, dst)
            os.lchown(dst, stats[ST_UID], stats[ST_GID])
            # Continue traversal...
            visitfiles(dir, self)
        else:
            # Create hard link in destination.
            odst = re.sub(self.old, self.dst, dir)
            os.link(dst, odst)

    def file(self, file):
        stats = os.lstat(file)
        old = re.sub(self.src, self.old, file)
        ostats = os.lstat(old)
        if stats[ST_INO] != ostats[ST_INO]:
            dst = re.sub(self.src, self.dst, file)
            # Copy file contents from snapshot to destination.
            shutil.copyfile(file, dst)
            # Copy the permissions and accessed/modified times.
            shutil.copystat(file, dst)
            # Copy the owner/group values to destination.
            os.lchown(dst, stats[ST_UID], stats[ST_GID])
        else:
            # Create hard link in destination.
            odst = re.sub(self.old, self.dst, file)
            os.link(dst, odst)

    def link(self, link):
        stats = os.lstat(link)
        old = re.sub(self.src, self.old, link)
        ostats = os.lstat(old)
        if stats[ST_INO] != ostats[ST_INO]:
            # Copy link to destination.
            lnk = os.readlink(link)
            dst = re.sub(self.src, self.dst, link)
            os.symlink(lnk, dst)
            os.lchown(dst, stats[ST_UID], stats[ST_GID])
        else:
            # Create hard link in destination.
            odst = re.sub(self.old, self.dst, link)
            os.link(dst, odst)

def sortbackups(path):
    """Returns a sorted list of Time Machine backups, with certain
       entries pruned from the list (Latest and *.inProgress)."""
    entries = os.listdir(path)
    okay = lambda s: s != "Latest" and not s.endswith(".inProgress")
    entries = [entry for entry in entries if okay(entry)]
    entries.sort()
    return entries

def usage():
    print "Usage: timecopy.py [-hv] <src> <dst>"
    print ""
    print "Copies a Mac OS X Time Machine volume (set of backups) from one location"
    print "to another, such as from one disk to another, or from one disk image to"
    print "another. This can be useful when block copying the disk is not feasible"
    print "(i.e. the destination disk is smaller than the original)."
    print ""
    print "The given <src> location must be the root directory of the source Time"
    print "Machine volume, that which contains the 'Backups.backupdb' directory"
    print "(e.g. /Volumes/Backup, not /Volumes/Backup/Backups.backupdb/gojira)."
    print "You must have sufficient privileges to access this directory, and the"
    print "Time Machine volume must already be mounted (read-only mode is okay)."
    print ""
    print "The <dst> location is (ideally) the root of an empty volume to which the"
    print "Time Machine backups will be copied. You must have sufficient privileges"
    print "to write to this location. Chances are you will need to be using `sudo`"
    print "to gain the necessary privileges, unless -n or --dry-run is given."
    print ""
    print "-h|--help"
    print "\tPrints this usage information."
    print ""
    print "-n|--dry-run"
    print "\tDo not make any changes to the destination volume."
    print "\tTODO: NOT YET IMPLEMENTED"
    print ""
    print "-v|--verbose"
    print "\tPrints information about what the script is doing at each step."
    print "\tTODO: NOT YET IMPLEMENTED"

def main():
    """The main program method which handles user input and kicks off
       the copying process."""

    # Parse the command line arguments.
    shortopts = "hnv"
    longopts = ["help", "dry-run" "verbose"]
    try:
        opts, args = getopt.getopt(sys.argv[1:], shortopts, longopts)
    except getopt.GetoptError, err:
        print str(err)
        sys.exit(2)
    verbose = False
    dryrun = False
    for o, v in opts:
        if o in ("-v", "--verbose"):
            verbose = True
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-n", "--dry-run"):
            dryrun = True
        else:
            assert False, "unhandled option"
    if len(args) != 2:
        usage()
        sys.exit(2)
    src = args[1]
    dst = args[2]
    mode = os.lstat(src)[ST_MODE]
    if S_ISDIR(mode):
        # Create destination if necessary.
        if not os.path.exists(dst):
            os.makedirs(dir)
        # TODO: copy bookkeeping files -- is it really necessary?
        # TODO: copy backups
        pass
    else:
        print '%s is not a directory!' % src

if __name__ == '__main__':
    print 'THIS IS A WORK IN PROGRESS, DO NOT EXPECT IT TO WORK! (XXX)'
    main()
