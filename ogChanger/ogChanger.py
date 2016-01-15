#!/usr/bin/python
#
# ogChanger.py
#
# Author:   Jared D. Baker <jared.baker@uwyo.edu>
# 
# Purpose:  To massively change NUID/NGID on filesystem
#           where explicit mappings can be used.
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

# Some simple GLOBALS
DEBUG=0
SYMLINK_OVERRIDE = False
VERBOSE = 0

def Print(xstring,verbose=0):
    if verbose <= VERBOSE:
        sys.stdout.write(xstring + "\n")
    return

def PrintError(xstring):
    sys.stderr.write("\nError: " + str(xstring) + "\n\n")
    return

def PrintWarn(xstring):
    sys.stderr.write("\nWarning: " + str(xstring) + "\n\n")
    return

def PrintDebug(xstring,debug=0):
    if debug <= DEBUG:
        sys.stderr.write("Debug[%d]: %s \n" % (int(debug),str(xstring)))
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
    # Implicitly do not change root user ownership
    if uid == 0: return -1
    if uid not in UID_MAP.keys():
        PrintWarn( "uid: %d not in the UID_MAP. Not changing user on %s" % (uid,pathname) )
        return -1
    return UID_MAP[uid]

def checkGID(gid):
    # Implicitly do not change root group ownership
    if gid == 0: return -1
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

    if ignore_uid: 
        new_uid = -1
    else: 
        new_uid = checkUID(uid)

    if ignore_gid: 
        new_gid = -1
    else: 
        new_gid = checkGID(gid)

    Print("(uid,gid) = (%d,%d)" % (new_uid,new_gid),verbose=2)
    PrintDebug("uid change: %d -> %d ; gid change: %d -> %d ; %s" % (uid,new_uid,gid,new_gid,top) , debug=3)
    Print(lvl*' ' + top,verbose=1)
    try:
        os.lchown(top,new_uid,new_gid)
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

            Print("(uid,gid) = (%d,%d)" %(new_uid,new_gid),verbose=2)
            PrintDebug("uid change: %d -> %d ; gid change: %d -> %d ; %s" % (uid,new_uid,gid,new_gid,pathname) , debug=3)
            Print((lvl+1)*' ' + pathname,verbose=1)

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
            Print("(uid,gid) = (%d,%d)" %(new_uid,new_gid),verbose=2)
            PrintDebug("uid change: %d -> %d ; gid change: %d -> %d ; %s" % (uid,new_uid,gid,new_gid,pathname) , debug=3)
            Print((lvl+1)*' ' + pathname,verbose=1)
            try:
                os.chown(pathname,new_uid,new_gid)
            except:
                PrintError( "chown: %s" % (pathname))
            continue

        # Don't do other types of files ... devices, character files, named pipes, etc.


def main():
    global DEBUG
    global SYMLINK_OVERRIDE
    global VERBOSE

    pvers = "%d.%d.%d"%(__MAJOR__,__MINOR__,__RELEASE__);
    parser = ap.ArgumentParser()

    parser.add_argument("-V","--version",action="version", version="%%(prog)s (%s)"%(pvers))

    parser.add_argument("-v","--verbose",action="count",default=0,help="scalable verbose output (STDOUT)")

    parser.add_argument("-D","--debug",action="count",default=0,help="scalable debugging output (STDERR)")

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

    DEBUG = args.debug
    PrintDebug("Debugging set at %d" % (DEBUG),debug=1)
    SYMLINK_OVERRIDE = args.follow_symlinks
    VERBOSE = args.verbose
    Print("verbose level = %d" % ( args.verbose ), verbose=1 )

    ignore_uid = args.ignore_uid
    ignore_gid = args.ignore_gid

    if args.dry_run is True:
        Print("Running in Dry-run mode")
        ignore_uid=True
        ignore_gid=True

    Print("")
    for each in args.dir:
        WalkDirTree( os.path.abspath(each), lvl=0,ignore_uid=ignore_uid,ignore_gid=ignore_gid)
        Print("")
    return 0

# Run the main app
if __name__ == "__main__": main()
