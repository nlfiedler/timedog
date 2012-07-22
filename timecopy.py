#!/usr/bin/python
#
# Copyright (c) 2009-2012 Nathan Fiedler
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
#
# Invoke this script with '--help' option for detailed description of
# what it does and how you can use it.
#
import errno
import getopt
import os
import os.path
import re
import shutil
import stat
import subprocess
import sys
import time
import xattr
import xattr.constants

#
# TODO: "too many open files" says get_tm_bandsize() on server the last time I tried using this
#


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
            mode = os.lstat(pathname)[stat.ST_MODE]
            if stat.S_ISDIR(mode):
                visitor.dir(pathname)
            elif stat.S_ISLNK(mode):
                visitor.link(pathname)
            elif stat.S_ISREG(mode):
                visitor.file(pathname)
            else:
                print 'WARNING: unknown file %s' % pathname
        except OSError, e:
            print "ERROR '{}' processing {}".format(e, pathname)


def chown(path, uid, gid):
    """Attempt to change the owner/group of the given file/directory using
       os.lchown(). If this fails due to insufficient permissions, display
       an appropriate error message and exit. Otherwise, raise the error."""
    try:
        # Use lchown so we do not follow symbolic links, just change the
        # target as specified by the caller.
        os.lchown(path, uid, gid)
        # Note that it is possible the destination volume was mounted with
        # the MNT_IGNORE_OWNERSHIP flag, in which case everything we create
        # there will be owned by the _unknown user and group, no matter what
        # we might want it to be. This is built into the XNU kernel.
    except OSError, e:
        if e.errno == errno.EPERM:
            # Strangely root has problems changing symlinks that point
            # to non-existent entries, need to filter out and ignore
            # (we are most likely copying to an external disk anyway,
            # in which case all files are owned by the _unknown user).
            mode = os.lstat(path)[stat.ST_MODE]
            if not stat.S_ISLNK(mode):
                # Sometimes mysteriously fails to chown directories.
                # Try again in one second; if it fails again ignore
                # the problem and move on.
                time.sleep(1)
                try:
                    os.chown(path, uid, gid)
                except OSError:
                    pass
        else:
            raise e


def link(src, dst):
    """Creates a hard link called 'dst' that points to 'src'.
       Ensures that the src entry exists and raises an error if not."""
    if os.path.exists(src):
        os.link(src, dst)
    else:
        raise OSError(errno.ENOENT, "%s missing!" % src)


def copyxattr(src, dst):
    """Copy the extended attributes from src to dst using xattr."""
    # See http://pypi.python.org/pypi/xattr for a (possibly outdated)
    # version of xattr. A (possibly newer) version is included with
    # Python on the Mac.
    sx = xattr.xattr(src)
    dx = xattr.xattr(dst)
    # Make sure not to follow symbolic links as we always work on the
    # links themselves, not the (possibly) non-existent target.
    attrs = sx.list(xattr.constants.XATTR_NOFOLLOW)
    try:
        for name in attrs:
            value = sx.get(name, xattr.constants.XATTR_NOFOLLOW)
            dx.set(name, value, xattr.constants.XATTR_NOFOLLOW)
    except IOError:
        # Fails for certain directories which we will ignore.
        # All others, show a warning.
        if not dst.endswith(("/etc", "/tmp", "/var")):
            print "WARNING: cannot xattr %s" % dst


class CopyInitialVisitor(TreeVisitor):
    """Copies a directory tree from one place to another."""

    def __init__(self, verbose, dryrun, extattr):
        """If verbose is True, display operations as they are performed
           If dryrun is True, do not make any modifications on disk.
           If extattr is True, just copy the extended attributes."""
        self.verbose = verbose
        self.dryrun = dryrun
        self.extattr = extattr

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
            chown(dst, stats[stat.ST_UID], stats[stat.ST_GID])
        if not self.dryrun or self.extattr:
            copyxattr(dir, dst)
        # Continue traversal...
        visitfiles(dir, self)

    def file(self, file):
        dst = re.sub(self.src, self.dst, file)
        if self.verbose:
            print "cp <%s> <%s>" % (file, dst)
        if not self.dryrun:
            try:
                # Copy file contents from snapshot to destination.
                shutil.copyfile(file, dst)
                # Copy the permissions and accessed/modified times.
                shutil.copystat(file, dst)
                # Copy the owner/group values to destination.
                stats = os.lstat(file)
                chown(dst, stats[stat.ST_UID], stats[stat.ST_GID])
            except IOError, e:
                print "ERROR '{}' processing file {}".format(e, file)
        if not self.dryrun or self.extattr:
            copyxattr(file, dst)

    def link(self, link):
        # Copy link to destination.
        lnk = os.readlink(link)
        dst = re.sub(self.src, self.dst, link)
        if self.verbose:
            print "ln -s <%s> <%s>" % (lnk, dst)
        if not self.dryrun:
            os.symlink(lnk, dst)
            stats = os.lstat(link)
            chown(dst, stats[stat.ST_UID], stats[stat.ST_GID])
        if not self.dryrun or self.extattr:
            copyxattr(link, dst)


class CopyBackupVisitor(TreeVisitor):
    """Copies a directory tree and its files, where those entries differ
       from a reference tree. That is, if any entry has the same inode
       value as the corresponding entry in the reference tree, a new
       hard link is made in the destination, and nothing further is
       done with that entry (directories are not traversed, files are
       not copied)."""

    def __init__(self, old, prev, curr, verbose, dryrun, extattr):
        """If verbose is True, display operations as they are performed
           If dryrun is True, do not make any modifications on disk.
           If extattr is True, just copy the extended attributes.
           old is the reference tree to which src will be compared.
           prev is the entry name of the previous backup.
           curr is the entry name of the backup being copied"""
        self.verbose = verbose
        self.dryrun = dryrun
        self.old = old
        self.prev = prev
        self.curr = curr
        self.extattr = extattr

    def copytree(self, src, dst):
        "Copy the tree rooted at src to dst"
        self.src = src
        self.dst = dst
        visitfiles(src, self)

    def dir(self, dir):
        stats = os.lstat(dir)
        old = re.sub(self.src, self.old, dir)
        try:
            ostats = os.lstat(old)
        except OSError, e:
            if e.errno in (errno.ENOENT, errno.ENOTDIR, errno.EISDIR):
                # File became directory, or vice versa, or just isn't there.
                ostats = None
            else:
                raise e
        dst = re.sub(self.src, self.dst, dir)
        if ostats is None or stats[stat.ST_INO] != ostats[stat.ST_INO]:
            if self.verbose:
                print "mkdir <%s>" % dst
            if not self.dryrun:
                # Create destination directory, copying stats and ownership.
                os.mkdir(dst)
                shutil.copystat(dir, dst)
                chown(dst, stats[stat.ST_UID], stats[stat.ST_GID])
            if not self.dryrun or self.extattr:
                copyxattr(dir, dst)
            # Continue traversal...
            visitfiles(dir, self)
        else:
            odst = re.sub(self.curr, self.prev, dst)
            if self.verbose:
                print "ln <%s> <%s>" % (dst, odst)
            if not self.dryrun:
                # Create hard link in destination.
                link(odst, dst)

    def file(self, file):
        stats = os.lstat(file)
        old = re.sub(self.src, self.old, file)
        dst = re.sub(self.src, self.dst, file)
        try:
            ostats = os.lstat(old)
        except OSError, e:
            if e.errno in (errno.ENOENT, errno.ENOTDIR, errno.EISDIR):
                # File became directory, or vice versa, or just isn't there.
                ostats = None
            else:
                raise e
        if ostats is None or stats[stat.ST_INO] != ostats[stat.ST_INO]:
            if self.verbose:
                print "cp <%s> <%s>" % (file, dst)
            if not self.dryrun:
                try:
                    # Copy file contents from snapshot to destination.
                    shutil.copyfile(file, dst)
                    # Copy the permissions and accessed/modified times.
                    shutil.copystat(file, dst)
                    # Copy the owner/group values to destination.
                    chown(dst, stats[stat.ST_UID], stats[stat.ST_GID])
                except IOError, e:
                    print "ERROR '{}' processing file {}".format(e, file)
            if not self.dryrun or self.extattr:
                copyxattr(file, dst)
        else:
            odst = re.sub(self.curr, self.prev, dst)
            if self.verbose:
                print "ln <%s> <%s>" % (dst, odst)
            if not self.dryrun:
                # Create hard link in destination.
                link(odst, dst)

    def link(self, link):
        stats = os.lstat(link)
        old = re.sub(self.src, self.old, link)
        dst = re.sub(self.src, self.dst, link)
        try:
            ostats = os.lstat(old)
        except OSError, e:
            if e.errno in (errno.ENOENT, errno.ENOTDIR, errno.EISDIR):
                # File became directory, or vice versa, or just isn't there.
                ostats = None
            else:
                raise e
        if ostats is None or stats[stat.ST_INO] != ostats[stat.ST_INO]:
            lnk = os.readlink(link)
            if self.verbose:
                print "ln -s <%s> <%s>" % (lnk, dst)
            if not self.dryrun:
                # Copy link to destination.
                os.symlink(lnk, dst)
                chown(dst, stats[stat.ST_UID], stats[stat.ST_GID])
            if not self.dryrun or self.extattr:
                copyxattr(link, dst)
        else:
            odst = re.sub(self.curr, self.prev, dst)
            if self.verbose:
                print "ln <%s> <%s>" % (dst, odst)
            if not self.dryrun:
                # Create hard link in destination.
                link(odst, dst)


def copybackupdb(srcbase, dstbase, verbose, dryrun, extattr):
    """Copy the backup database found in srcbase to dstbase."""
    # Validate that srcbase contains a backup database.
    srcdb = os.path.join(srcbase, 'Backups.backupdb')
    if not os.path.exists(srcdb):
        print "ERROR: %s does not contain a Time Machine backup!" % srcbase
        sys.exit(2)
    dstdb = os.path.join(dstbase, 'Backups.backupdb')
    # Get a list of entries in the backupdb (typically just one).
    hosts = os.listdir(srcdb)

    def goodhost(host):
        src = os.path.join(srcdb, host)
        mode = os.lstat(src)[stat.ST_MODE]
        if len(host) > 0 and host[0] != '.' and stat.S_ISDIR(mode):
            return True
        return False
    hosts = [host for host in hosts if goodhost(host)]
    for host in hosts:
        # Get the list of backup snapshots sorted by name (i.e. date).
        src = os.path.join(srcdb, host)
        entries = os.listdir(src)

        def goodsnap(snap):
            if snap == '.DS_Store' or snap == 'Latest'\
                    or snap.endswith('.inProgress'):
                return False
            return True
        entries = [entry for entry in entries if goodsnap(entry)]
        entries.sort()

        def mkdest(source, target):
            stats = os.lstat(source)
            if verbose:
                print "mkdir <%s>" % target
            if not dryrun:
                os.makedirs(target)
                shutil.copystat(source, target)
                chown(target, stats[stat.ST_UID], stats[stat.ST_GID])
            if not dryrun or extattr:
                copyxattr(source, target)
        # Copy initial backup.
        dst = os.path.join(dstdb, host)
        srcbkup = os.path.join(src, entries[0])
        dstbkup = os.path.join(dst, entries[0])
        if not extattr and os.path.exists(dstbkup):
            print "%s already exists, skipping..." % entries[0]
        else:
            mkdest(srcbkup, dstbkup)
            visitor = CopyInitialVisitor(verbose, dryrun, extattr)
            print "Copying backup %s -- this may take a while..." % entries[0]
            visitor.copytree(srcbkup, dstbkup)
        # Copy all subsequent backup snapshots.
        prev = entries[0]
        for entry in entries[1:]:
            # Here previous is the backup before the one we are about to
            # copy; it is used to determine which entries are hard links.
            previous = srcbkup
            srcbkup = os.path.join(src, entry)
            dstbkup = os.path.join(dst, entry)
            if not extattr and os.path.exists(dstbkup):
                print "%s already exists, skipping..." % entry
            else:
                mkdest(srcbkup, dstbkup)
                visitor = CopyBackupVisitor(previous, prev, entry,
                                            verbose, dryrun, extattr)
                print "Copying backup %s..." % entry
                visitor.copytree(srcbkup, dstbkup)
            prev = entry
        # Create Latest symlink pointing to last entry.
        latest = os.path.join(dst, 'Latest')
        if verbose:
            print "ln -s <%s> <%s>" % (entries[-1], latest)
        if not dryrun:
            if os.path.lexists(latest):
                # Seems root cannot delete the symlink, so have the real
                # user perform the delete for us.
                user = subprocess.Popen(["who", "am", "i"],
                        stdout=subprocess.PIPE).communicate()[0]
                user = user.split()[0]
                os.system("sudo -u %s unlink %s" % (user, latest))
            os.symlink(entries[-1], latest)
    # Copy the MAC address dotfile(s) that TM creates.
    entries = os.listdir(srcbase)
    regex = re.compile('^\.[0-9a-f]{12}$')
    for entry in entries:
        if regex.match(entry):
            src = os.path.join(srcbase, entry)
            dst = os.path.join(dstbase, entry)
            if verbose:
                print "cp <%s> <%s>" % (src, dst)
            if not dryrun:
                try:
                    shutil.copyfile(src, dst)
                    shutil.copystat(src, dst)
                    stats = os.lstat(src)
                    chown(dst, stats[stat.ST_UID], stats[stat.ST_GID])
                except IOError, e:
                    print "ERROR '{}' processing file {}".format(e, src)
            if not dryrun or extattr:
                copyxattr(src, dst)


def usage():
    print """Usage: timecopy.py [-hnvx] [--nochown] <source> <target>

Copies a Mac OS X Time Machine volume (set of backups) from one location
to another, such as from one disk to another, or from one disk image to
another. This can be useful when block copying the disk is not feasible
(i.e. the destination disk is smaller than the original).

The <source> location must be the root directory of the source Time
Machine volume, that which contains the 'Backups.backupdb' directory
(e.g. /Volumes/Backup, not /Volumes/Backup/Backups.backupdb/gojira).
You must have sufficient privileges to access this directory, and the
Time Machine volume must already be mounted (read-only mode is okay).

The <target> location should be the root of an empty volume to which the
Time Machine backups will be copied. You must have sufficient privileges
to write to this location. Chances are you will need to be using `sudo`
to gain the necessary privileges, unless -n or --dry-run is given.

-h|--help
\tPrints this usage information.

-n|--dry-run
\tDo not make any changes on disk.

--nochown
\tDo not use chown to change the owner/group of the destination
\tfiles. Generally only root can do that, and on network volumes
\tthe Mac will make everything owned by the 'unknown' user anyway.

-v|--verbose
\tPrints information about what the script is doing at each step.

-x|--xattr
\tCopies the extended attributes from the source volume to the target
\tvolume, assuming that the target is an exact copy of the source.
\tThis is useful if you have a copy of a Time Machine volume that is
\tmissing the necessary extended attributes. Normally this script
\twill already have copied the extended attributes as part of the
\tcopying process, so this option is only needed when you have created
\tthe copy using some other means."""


def main():
    """The main program method which handles user input and kicks off
       the copying process."""

    # Parse the command line arguments.
    shortopts = "hnvx"
    longopts = ["help", "dry-run", "nochown", "verbose", "xattr"]
    try:
        opts, args = getopt.getopt(sys.argv[1:], shortopts, longopts)
    except getopt.GetoptError, err:
        print str(err)
        print "Invoke with -h for help."
        sys.exit(2)
    verbose = False
    dryrun = False
    extattr = False
    for opt, val in opts:
        if opt in ("-v", "--verbose"):
            verbose = True
        elif opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-n", "--dry-run"):
            dryrun = True
        elif opt == '--nochown':
            # Nullify the chown function defined above.
            global chown
            chown = lambda path, uid, gid: ""
        elif opt in ("-x", "--xattr"):
            extattr = True
            # Copying only the extended attributes means that no other
            # file system changes will be made in the process.
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
        copybackupdb(src, dst, verbose, dryrun, extattr)
    except KeyboardInterrupt:
        print "Exiting..."
        sys.exit(1)

if __name__ == '__main__':
    main()
