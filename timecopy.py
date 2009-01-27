#!/usr/bin/python
#
# Copyright (c) 2009 Nathan Fiedler
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
# Invoke this script with '--help' option for detailed description of
# what it does and how you can use it.
#
# TODO EVENTUALLY
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# - Allow resuming a copy of a directory tree
#   - Check for incomplete copies
#   - Only copy what hasn't been done already
# - Handle errors gracefully
#   - Report the errors and keep going
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
import getopt
import os
import os.path
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
                print 'WARNING: unknown file %s' % pathname
        except OSError:
            print 'ERROR: reading %s' % pathname
            # XXX: should stop now or keep going?

class CopyInitialVisitor(TreeVisitor):
    """Copies a directory tree from one place to another."""

    def __init__(self, verbose, dryrun):
        """If verbose is True, display operations as they are performed
           If dryrun is True, do not make any modifications on disk."""
        self.verbose = verbose
        self.dryrun = dryrun

    def copytree(self, src, dst):
        """Copies the directory tree rooted at src to dst."""
        self.src = src
        self.dst = dst
        visitfiles(src, self)

    def dir(self, dir):
        # Create destination directory, copying stats and ownership.
        dst = re.sub(self.src, self.dst, dir)
        if self.verbose:
            print "mkdir <%s>" % dst
        if not self.dryrun:
            os.mkdir(dst)
            shutil.copystat(dir, dst)
            stats = os.lstat(dir)
            os.chown(dst, stats[ST_UID], stats[ST_GID])
        # Continue traversal...
        visitfiles(dir, self)

    def file(self, file):
        dst = re.sub(self.src, self.dst, file)
        if self.verbose:
            print "cp <%s> <%s>" % (file, dst)
        if not self.dryrun:
            # Copy file contents from snapshot to destination.
            shutil.copyfile(file, dst)
            # Copy the permissions and accessed/modified times.
            shutil.copystat(file, dst)
            # Copy the owner/group values to destination.
            stats = os.lstat(file)
            os.chown(dst, stats[ST_UID], stats[ST_GID])

    def link(self, link):
        # Copy link to destination.
        lnk = os.readlink(link)
        dst = re.sub(self.src, self.dst, link)
        if self.verbose:
            print "ln -s <%s> <%s>" % (lnk, dst)
        if not self.dryrun:
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

    def __init__(self, old, verbose, dryrun):
        """If verbose is True, display operations as they are performed
           If dryrun is True, do not make any modifications on disk.
           old is the reference tree to which src will be compared."""
        self.verbose = verbose
        self.dryrun = dryrun
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
            if self.verbose:
                print "mkdir <%s>" % dst
            if not self.dryrun:
                # Create destination directory, copying stats and ownership.
                os.mkdir(dst)
                shutil.copystat(dir, dst)
                os.chown(dst, stats[ST_UID], stats[ST_GID])
            # Continue traversal...
            visitfiles(dir, self)
        else:
            odst = re.sub(self.old, self.dst, dir)
            if self.verbose:
                print "ln <%s> <%s>" % (dst, odst)
            if not self.dryrun:
                # Create hard link in destination.
                os.link(dst, odst)

    def file(self, file):
        stats = os.lstat(file)
        old = re.sub(self.src, self.old, file)
        dst = re.sub(self.src, self.dst, file)
        ostats = os.lstat(old)
        if stats[ST_INO] != ostats[ST_INO]:
            if self.verbose:
                print "cp <%s> <%s>" % (file, dst)
            if not self.dryrun:
                # Copy file contents from snapshot to destination.
                shutil.copyfile(file, dst)
                # Copy the permissions and accessed/modified times.
                shutil.copystat(file, dst)
                # Copy the owner/group values to destination.
                os.chown(dst, stats[ST_UID], stats[ST_GID])
        else:
            odst = re.sub(self.old, self.dst, file)
            if self.verbose:
                print "ln <%s> <%s>" % (dst, odst)
            if not self.dryrun:
                # Create hard link in destination.
                os.link(dst, odst)

    def link(self, link):
        stats = os.lstat(link)
        old = re.sub(self.src, self.old, link)
        dst = re.sub(self.src, self.dst, link)
        ostats = os.lstat(old)
        if stats[ST_INO] != ostats[ST_INO]:
            lnk = os.readlink(link)
            if self.verbose:
                print "ln -s <%s> <%s>" % (lnk, dst)
            if not self.dryrun:
                # Copy link to destination.
                os.symlink(lnk, dst)
                os.lchown(dst, stats[ST_UID], stats[ST_GID])
        else:
            odst = re.sub(self.old, self.dst, link)
            if self.verbose:
                print "ln <%s> <%s>" % (dst, odst)
            if not self.dryrun:
                # Create hard link in destination.
                os.link(dst, odst)

def copybackupdb(srcbase, dstbase, verbose, dryrun):
    """Copy the backup database found in srcbase to dstbase."""
    # Validate that srcbase contains a backup database.
    srcdb = os.path.join(srcbase, 'Backups.backupdb')
    if not os.path.exists(srcdb):
        print "ERROR: %s does not contain a Time Machine backup!" % srcbase
        sys.exit(2)
    dstdb = os.path.join(dstbase, 'Backups.backupdb')
    # XXX: what about the bookkeeping files at the root?
    # Get a list of entries in the backupdb (typically just one).
    hosts = os.listdir(srcdb)
    for host in hosts:
        # Get the list of backup snapshots sorted by name (i.e. date).
        src = os.path.join(srcdb, host)
        entries = os.listdir(src)
        okay = lambda s: s != "Latest" and not s.endswith(".inProgress")
        entries = [entry for entry in entries if okay(entry)]
        entries.sort()
        def mkdest(source, target):
            stats = os.lstat(source)
            if verbose:
                print "mkdir <%s>" % target
            if not dryrun:
                os.mkdir(target)
                shutil.copystat(source, target)
                os.chown(target, stats[ST_UID], stats[ST_GID])
        # Copy initial backup.
        dst = os.path.join(dstdb, host)
        srcbkup = os.path.join(src, entries[0])
        dstbkup = os.path.join(dst, entries[0])
        mkdest(srcbkup, dstbkup)
        visitor = CopyInitialVisitor(verbose, dryrun)
        print "Copying backup %s -- this will take a while..." % entries[0]
        visitor.copytree(srcbkup, dstbkup)
        # Copy all subsequent backup snapshots.
        for entry in entries[1:]:
            # Here previous is the backup before the one we are about to
            # copy; it is used to determine which entries are hard links.
            previous = srcbkup
            srcbkup = os.path.join(src, entry)
            dstbkup = os.path.join(dst, entry)
            mkdest(srcbkup, dstbkup)
            visitor = CopyBackupVisitor(previous, verbose, dryrun)
            print "Copying backup %s..." % entries[0]
            visitor.copytree(srcbkup, dstbkup)

def usage():
    print "Usage: timecopy.py [-hnv] <source> <target>"
    print ""
    print "Copies a Mac OS X Time Machine volume (set of backups) from one location"
    print "to another, such as from one disk to another, or from one disk image to"
    print "another. This can be useful when block copying the disk is not feasible"
    print "(i.e. the destination disk is smaller than the original)."
    print ""
    print "The <source> location must be the root directory of the source Time"
    print "Machine volume, that which contains the 'Backups.backupdb' directory"
    print "(e.g. /Volumes/Backup, not /Volumes/Backup/Backups.backupdb/gojira)."
    print "You must have sufficient privileges to access this directory, and the"
    print "Time Machine volume must already be mounted (read-only mode is okay)."
    print ""
    print "The <target> location should be the root of an empty volume to which the"
    print "Time Machine backups will be copied. You must have sufficient privileges"
    print "to write to this location. Chances are you will need to be using `sudo`"
    print "to gain the necessary privileges, unless -n or --dry-run is given."
    print ""
    print "-h|--help"
    print "\tPrints this usage information."
    print ""
    print "-n|--dry-run"
    print "\tDo not make any changes on disk."
    print ""
    print "-v|--verbose"
    print "\tPrints information about what the script is doing at each step."

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
        print "Invoke with -h for help."
        sys.exit(2)
    verbose = False
    dryrun = False
    for opt, val in opts:
        if opt in ("-v", "--verbose"):
            verbose = True
        elif opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-n", "--dry-run"):
            dryrun = True
        else:
            assert False, "unhandled option: %s" % opt
    if len(args) != 2:
        print "Missing required arguments. Invoke with -h for help."
        sys.exit(2)
    # Check that the given source and destination exist.
    src = args[0]
    if not os.path.exists(src):
        print "%s does not exist!" % src
        sys.exit(1)
    if not os.path.isdir(src):
        print "%s is not a directory!" % src
        sys.exit(1)
    dst = args[1]
    if not os.path.exists(dst):
        print "%s does not exist!" % dst
        sys.exit(1)
    if not os.path.isdir(dst):
        print "%s is not a directory!" % dst
        sys.exit(1)
    try:
        copybackupdb(src, dst, verbose, dryrun)
    except KeyboardInterrupt:
        print "Exiting..."
        sys.exit(1)

if __name__ == '__main__':
    print 'THIS IS A WORK IN PROGRESS, DO NOT EXPECT IT TO WORK! (XXX)'
    main()
