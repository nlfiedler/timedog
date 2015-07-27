# Introduction #

The timecopy.py script is a tool that makes a faithful copy of a Time Machine volume to a new disk (or disk image). It can be useful if you need to recover from a file system error, such as the dreaded **invalid sibling link** error, in which you can probably read the backups but you cannot create new ones. If this is the case, most of the disk repair tools cannot fix this particular error (some people have had luck with fsck and Disk Warrior), so you are left with having to make a copy of the corrupt disk (image). Using a tool that performs a block-for-block copy will in fact copy the file system error to the new disk, which is of no use at all. What's needed is a way to copy the file system to a new location using traditional file copy. The only problem with that is the Time Machine backups are full of hard links, which will appear as normal files and directories, and performing a simple file copy will result in an enormous waste of disk space.

This is where the timecopy.py script comes in. It understands the format of the Time Machine volumes and will intelligently reproduce the backups, to be best of its ability, in a new location. This includes all of the hard links, backed up files, and the extended attributes that form the basis of the "magic" of Time Machine.

# Getting Started #

This procedure is not for the faint of heart, and involves use of the command line and running scripts as the root user. If you have any doubts, stop now. Likewise, this script is **not guaranteed to work**. In fact, the author makes no guarantee that it will not cause harm. While every step has been taken to prevent such an event, use of this script is at **your own risk**. With that being said, it has been tested on multiple systems and found to work as expected.

Make backups. Before going any further, make sure you have saved your important data to removable media that is locked away in a safe place. Who knows, your computer may catch on fire while using this script. Okay, probably not, but please do make backups.

# Using timecopy #

So you need to make a copy of a Time Machine volume, and you want to use timecopy. Now what? Start by determining the size of your Time Machine volume and locating a disk, or some free space where you can create a disk image, that has enough room to hold a copy of the Time Machine backups. If you have another disk that you can use, make sure it is formatted with the HFS+J disk format. That is, it must be HFS+ and have journaling enabled (just like the disk used for Time Machine).

Next, either attach that disk and ensure it is in HFS+J format, or create a disk image to hold the copy of your TM volume. I recommend creating a disk image using the following command, entered in the Terminal window (Terminal is found in `/Applications/Utilities`):

```
sudo hdiutil create -nospotlight -type SPARSEBUNDLE -imagekey \
  sparse-band-size=131072 -size 300g -fs "HFS+J" -volname "NewBackup" \
  mymac_012345678987.sparsebundle
```

  * In place of the "300g" argument, enter whatever size you want for the new volume. The typical recommendation is twice the size of your system disk. The 'g' stands for gigabytes. See the hdiutil man page (`man hdiutil`) for more details.
  * In place of the "mymac" name, enter the host name of your computer, as found with the command: `hostname -s`
  * In place of the "012345678987" sequence, enter the MAC address of your computer, as found with the command: `ifconfig en0 | grep "ether" | sed 's/://g' | awk '{print $2}'`
  * When prompted, enter the password for your user account, which authenticates you and allows you to run the `hdiutil` command as the root user.
  * If you are using a remote server to hold your TM backups, you can now move the disk image to that server. Note that you (probably) cannot create the disk image directly on the remote server.

Now, "attach" the disk image so it is visible.

```
sudo hdiutil attach -noverify -noautofsck /path/to/mymac_012345678987.sparsebundle
```

  * The command options are there to avoid the expense of scanning and verifying the disk image, which you almost never need to do anyway.
  * At this point you should see the new backup volume mounted under `/Volumes` on your computer.

If your original TM volume is not mounted yet, do so now. If you have a corrupt volume, you may need to mount it in read-only mode. Chances are, when you try to mount it, the file system check will show an error and mount it in read-only form anyway. If this volume is on a remote share, you can quickly mount it this way:

```
sudo hdiutil attach -noverify -noautofsck -readonly /path/to/mymac_012345678987.sparsebundle
```

Finally, after all of that, you can run the [timecopy.py](http://timedog.googlecode.com/svn/trunk/timecopy.py) script (click the link to download the script).

```
sudo timecopy.py /Volumes/OldBackup /Volumes/NewBackup
```

Now, depending on how large your Time Machine volume is, prepare to wait a long time for the copy to complete. If you see any warnings about xattr not working, you can probably ignore them. Most of the time it's just Finder information associated with a file or directory.

Once the copy is complete, you should be able to point Time Machine to the new volume, make new backups and browse the backup history as usual.