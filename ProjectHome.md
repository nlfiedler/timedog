timedog is a Perl script that displays the set of files that were saved for any given backup created by Mac OS X Time Machine. By default it shows those files that were saved in the most recent backup. The listing includes the file sizes before and after, as well as a total file count and size. The script includes an option to summarize changes to a particular directory depth, producing a more concise display, helping to get an understanding of which areas of your system are taking up the most space in the backups.  It can also sort by size, and/or omit files below a given size.

## Usage ##

  1. Open Terminal (in `/Applications/Utilities`)
  1. `/path/to/timedog -d 5 -l`
    * For instance, if you unzipped `timedog` to your Desktop, the path would be `~/Desktop/timedog`

The example above uses the options `-d 5 -l` which will summarize the changes up to five directory levels deep, and hide rows that pertain to symbolic links. These links are often meaningless and can safely be ignored.

By default `timedog` shows the file changes in the most recent backup.  It locates and changes to your Time Machine directory automatically (typically `/Volumes/Time\ Machine/Backups.backupdb/[Computer Name]`).  Timestamped backup directories like `2013-05-01-163402` can be passed to `timedog` as an argument:

  * `/path/to/timedog -d 5 -l 2013-05-01-163402`

You can get a list of these with the `-t` option:

  * `/path/to/timedog -t`

Below is an example of the output.

```
$ ~/Desktop/timedog -d 5 -l
==> Comparing TM backup 2009-01-15-080533 to 2009-01-15-070632
    1.6KB->    2.9KB        /.Backup.log
       0B->       0B        /.com.apple.TMCheckpoint
     956B->     956B        /.exclusions.plist
       0B->       0B        /Macintosh HD/.com.apple.timemachine.supported
    1.1KB->    1.1KB        /Macintosh HD/private/var/db/.TimeMachine.Results.plist
    1.1KB->    1.1KB    [1] /Macintosh HD/private/var/db/
   12.0KB->   12.0KB        /Macintosh HD/Users/nfiedler/.DS_Store
    6.5MB->    6.6MB   [26] /Macintosh HD/Users/nfiedler/Library/Application Support/
       0B->     245B    [1] /Macintosh HD/Users/nfiedler/Library/Favorites/
   40.3KB->   42.7KB   [29] /Macintosh HD/Users/nfiedler/Library/Preferences/
    1.4MB->    1.4MB   [27] /Macintosh HD/Users/nfiedler/Library/Thunderbird/
==> Total Backup: 111 changed files/directories, 8.08MB
```

The number in square brackets (e.g. `[26]`) indicates the number of files and/or directories that changed within that particular directory tree. So in the example above, 26 entries under `Application Support` where changed.

## Time Machine over the Network ##

If you are using Time Machine over the network, such as with the Time Capsule product, you will probably need to mount the backup disk image before you can use the `timedog` script. To do this, open the Disk Utility application (from Spotlight, type "disk utility" and press Enter; or use Finder navigate to `/Applications/Utilities` and launch Disk Utility), then open Finder and navigate to the network share that contains your backup image. Select and drag the disk image to the Disk Utility window and drop it. You should then see the image name in left pane of the Disk Utility window. Now select that row and click the **Open** button in the toolbar. A small window will appear that shows the progress. When it shows "verifying", click the **Skip** button; another dialog appears to report a warning, just click **Ok**.

At this point you will have the Time Machine backup image mounted and available for browsing. You can now follow the example usage shown in the above section.

## Copying Time Machine volumes ##

If you have a need to copy a Time Machine volume without using a disk block copy utility, then [timecopy.py](http://timedog.googlecode.com/svn/trunk/timecopy.py) might be for you. See the UsingTimecopy page for details on how this script can be used and why.

## Files Accessibility ##

If your time machine backup includes files which are not reachable or readable as a normal user, you should run `timedog` using `sudo`

# `sudo /path/to/timedog -d 5 -l`