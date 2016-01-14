#!/usr/bin/python
#
# ogChanger.py
#
# Author:   Jared D. Baker <jared.baker@uwyo.edu>
# 
# Purpose:  To massively change NUID/NGID on filesystem
#           where explicit mappings can be used.
#
# Notes:    Highly likely not to work in Python3. Abstract prints later.
#
__MAJOR__ = 0
__MINOR__ = 1
__RELEASE__ = 0

import os, sys
import stat
import argparse as ap

# 
# Beg Example Mappings - use a file to construct a larger mapping
#
UID_MAP = {}
UID_MAP[0]     = 0
UID_MAP[20044] = 20044

GID_MAP = {}
GID_MAP[0]     = 0
GID_MAP[20044] = 80000
GID_MAP[80000] = 20044
#
# End Example Mappings
#


SYMLINK_OVERRIDE = False

def PrintError(xstring):
    sys.stderr.write("\nError: " + str(xstring) + "\n\n")
    return

def PrintWarn(xstring):
    sys.stderr.write("\nWarning: " + str(xstring) + "\n\n")
    return

def CheckLinkDir(mode,dir):
    # Be careful, mode must come from lstat, NOT stat.
    if stat.S_ISLNK(mode):
        if SYMLINK_OVERRIDE: return 0
        PrintError("No symlink traversing: %s -> %s" % (dir, os.path.join(dir, os.readlink(dir))))
        return 2
    
    if not stat.S_ISDIR(mode):
        PrintError("notdir: %s" % (dir))
        return 1
    return 0

def checkUID(uid):
    if uid not in UID_MAP.keys():
        PrintWarn( "uid: %d not in the UID_MAP. Not changing user on %s" % (uid,pathname) )
        return -1
    return UID_MAP[uid]

def checkGID(gid):
    if gid not in GID_MAP.keys():
        PrintWarn( "gid: %d not in the GID_MAP. Not changing group on %s" % (gid,pathname) )
        return -1
    return GID_MAP[gid]

def WalkDirTree(top,lvl=0,ignore_uid=False,ignore_gid=False):
    tstat = os.lstat(top)
    mode = tstat.st_mode
    uid = tstat.st_uid
    gid = tstat.st_gid

    result = CheckLinkDir(mode,top)
    if 0 < result: return result

    print lvl*' ' + top
    try:
        os.lchown(top,UID_MAP[uid],GID_MAP[gid])
    except:
        PrintError( "chown: %s" % (top) )

    for f in os.listdir(top):
        pathname = os.path.join(top,f)
        fstat = os.lstat(pathname)
        mode = fstat.st_mode
        uid = fstat.st_uid
        gid = fstat.st_gid

        if ignore_uid:
            new_uid = -1
        else:
            new_uid = checkUID(uid)

        if ignore_gid:
            new_gid = -1
        else:
            new_gid = checkGID(gid)

        if 0 < stat.S_ISLNK(mode):
        #if os.path.islink(pathname):
            # I shouldn't need the warning anymore, symlinks now managed as per man 2 lchown
            drflink = os.readlink(pathname)
            abslink = os.path.join(top,drflink)
            
            PrintWarn( "symlink: %s -> %s" % (pathname,abslink))
            os.lchown(pathname,new_uid,new_gid)

            if SYMLINK_OVERRIDE:
                drfstat = os.lstat(abslink)
                drfmode = drfstat.st_mode
                if 0 < stat.S_ISDIR(drfmode):
                    WalkDirTree(pathname,lvl=lvl+1)
            continue

        if 0 < stat.S_ISDIR(mode):
            WalkDirTree(pathname,lvl=lvl+1,ignore_uid=ignore_uid,ignore_gid=ignore_gid)
            continue

        if stat.S_ISREG(mode):
            print (lvl+1)*' ' + pathname
            try:
                os.chown(pathname,UID_MAP[uid],GID_MAP[gid])
            except:
                PrintError( "chown: %s" % (pathname))
            continue

        # Don't do other types of files ... devices, character files, named pipes, etc.


def main():
    global SYMLINK_OVERRIDE
    pvers = "%d.%d.%d"%(__MAJOR__,__MINOR__,__RELEASE__);
    parser = ap.ArgumentParser()

    parser.add_argument("-V","--version",action="version", version="%%(prog)s (%s)"%(pvers))

    parser.add_argument("-v","--verbose",action="count",help="scalable verbose output")

    parser.add_argument("-d","--dry-run",action="store_true",default=False,
            help="Do a dry run. Still scans all the metadata and calls the chown, but with non-changing values.")

    parser.add_argument("-iu","--ignore-uid",action="store_true",default=False,
            help="Do NOT change the UID of the files")

    parser.add_argument("-ig","--ignore-gid",action="store_true",default=False,
            help="Do NOT change the GID of the files")
    
    parser.add_argument("dir", type=str, nargs='+',help="directories to recursively modify permissions")
    
    parser.add_argument("-s","--follow-symlinks",action="store_true",default=False,
            help="Follow symbolic links. WARNING: May cause large overhead and repeat system calls!")
    
    args = parser.parse_args()

    SYMLINK_OVERRIDE = args.follow_symlinks

    ignore_uid = args.ignore_uid
    ignore_gid = args.ignore_gid

    if args.dry_run is True:
        ignore_uid=True
        ignore_gid=True

    print ""
    for each in args.dir:
        WalkDirTree( os.path.abspath(each), lvl=0,ignore_uid=ignore_uid,ignore_gid=ignore_gid)
        print ""
    return 0

    
if __name__ == "__main__": main()
