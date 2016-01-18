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
import ConfigParser as cp

from multiprocessing import Pool,JoinableQueue

MAP = { 
        'uid': {}, 
        'gid': {}
        }

# Aliases for the MAP dictionary right now:
UID_MAP = MAP['uid']
GID_MAP = MAP['gid']

# Some simple GLOBALS
DEBUG=0
SYMLINK_OVERRIDE = False
VERBOSE = 0

def PrintUsage():
    return

def PrintMapExample():
    sys.stdout.write("\n" + "\n".join("""
    [uid]
    1000=300000
    1005=300001
    [gid]
    1000=300000
    1005=300000
    5000=1000000
    5001=1000001
    """.split() ) + "\n\n")
    return

def Print(xstring,verbose=0):
    if verbose <= VERBOSE:
        sys.stdout.write(xstring + "\n")
    return

def PrintError(xstring):
    sys.stderr.write("Error: " + str(xstring) + "\n")
    return

def PrintWarn(xstring):
    sys.stderr.write("Warning: " + str(xstring) + "\n")
    return

def PrintDebug(xstring,debug=0):
    if debug <= DEBUG:
        sys.stderr.write("Debug[%d]: %s \n" % (int(debug),str(xstring)))
    return

def GenerateMap(map_file=""):
    global MAP
    
    if map_file == "":
        PrintError("map_file call is empty, please specify the map file")
        return 1

    if not os.path.isfile(map_file):
        PrintError("Map file '%s' does not exist. Check map file location." %(map_file))
        return 2

    parser = cp.ConfigParser()
    parser.read(map_file)
    sections = ['uid','gid']
    for s in sections:
        if s not in parser.sections():
            PrintError("There is no %s section defined in the map file. Exiting.")
            sys.exit(1)
        for name,value in parser.items(s):
            MAP[s][ int(name) ] = int(value)
    return 0

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

def checkID(tid,nid):
    if nid == 0: return 0
    try:
        new_id = MAP[tid][nid]
        return new_id
    except KeyError:
        PrintDebug("KeyError: no %s mapping from %d. Setting to -1." % (tid,nid),debug=1)
        return -1

def WalkDirTree(top,lvl=0,ignore_uid=False,ignore_gid=False):
    CHOWN = False
    tstat = os.lstat(top)
    mode = tstat.st_mode
    uid = tstat.st_uid
    gid = tstat.st_gid

    result = CheckLinkDir(mode,top)
    if 0 < result: return result

    if ignore_uid: 
        new_uid = -1
    else: 
        new_uid = checkID('uid',uid)
        if -1 == new_uid:
            PrintWarn("%s: %d not in the %s map. Not changing %s on %s" % ('uid',uid,'uid','uid',top))

    if ignore_gid: 
        new_gid = -1
    else: 
        new_gid = checkID('gid',gid)
        if -1 == new_gid:
            PrintWarn("%s: %d not in the %s map. Not changing %s on %s" % ('gid',gid,'gid','gid',top))

    Print("(uid,gid) = (%d,%d)" % (new_uid,new_gid),verbose=3)
    PrintDebug("uid change: %d -> %d ; gid change: %d -> %d ; %s" % (uid,new_uid,gid,new_gid,top), debug=3)

    if -2 != new_uid + new_gid: CHOWN=True

    Print(lvl*' ' + top,verbose=1)
    try:
        if CHOWN: os.lchown(top,new_uid,new_gid)
    except:
        PrintError( "chown: Likely have incorrect permissions to change %s" % (top) )

    for f in os.listdir(top):
        pathname = os.path.join(top,f)
        fstat = os.lstat(pathname)
        mode = fstat.st_mode
        uid = fstat.st_uid
        gid = fstat.st_gid
        
        # If directory, walk recursively, but avoid extra uid/gid checking.
        if 0 < stat.S_ISDIR(mode):
            WalkDirTree(pathname,lvl=lvl+1,ignore_uid=ignore_uid,ignore_gid=ignore_gid)
            continue

        if ignore_uid:
            new_uid = -1
        else:
            new_uid = checkID('uid',uid)
            if -1 == new_uid:
                PrintWarn("%s: %d not in the %s map. Not changing %s on %s" % ('uid',uid,'uid','uid',pathname))

        if ignore_gid:
            new_gid = -1
        else:
            new_gid = checkID('gid',gid)
            if -1 == new_gid:
                PrintWarn("%s: %d not in the %s map. Not changing %s on %s" % ('gid',gid,'gid','gid',pathname))

        if -2 != (new_uid + new_gid): CHOWN = True

        if 0 < stat.S_ISLNK(mode):
        #if os.path.islink(pathname):
            # I shouldn't need the warning anymore, symlinks now managed as per man 2 lchown
            drflink = os.readlink(pathname)
            abslink = os.path.join(top,drflink)
            
            PrintWarn( "symlink: %s -> %s" % (pathname,abslink))

            Print("(uid,gid) = (%d,%d)" %(new_uid,new_gid),verbose=2)
            PrintDebug("uid change: %d -> %d ; gid change: %d -> %d ; %s" % (uid,new_uid,gid,new_gid,pathname) , debug=3)
            Print((lvl+1)*' ' + pathname,verbose=1)

            try:
                if CHOWN: os.lchown(pathname,new_uid,new_gid)
            except:
                PrintError("chown: Likely have incorrect permissions to change %s" % (pathname))

            if SYMLINK_OVERRIDE:
                drfstat = os.lstat(abslink)
                drfmode = drfstat.st_mode
                if 0 < stat.S_ISDIR(drfmode):
                    WalkDirTree(pathname,lvl=lvl+1)
            continue

        if stat.S_ISREG(mode):
            Print("(uid,gid) = (%d,%d)" %(new_uid,new_gid),verbose=3)
            PrintDebug("uid change: %d -> %d ; gid change: %d -> %d ; %s" % (uid,new_uid,gid,new_gid,pathname) , debug=3)
            Print((lvl+1)*' ' + pathname,verbose=1)
            try:
                if CHOWN: os.chown(pathname,new_uid,new_gid)
            except:
                PrintError( "chown: Likely have incorrect permssions to change %s" % (pathname))
            continue

        # Don't do other types of files ... devices, character files, named pipes, etc.

def q_process_dir(q,dir_name,ignore_uid,ignore_gid):
    for each in os.listdir(dir_name):
        abs_fname = os.path.abspath( os.path.join(dir_name,each) )
        Print(abs_fname,verbose=0)
        q_process_file(q,abs_fname,ignore_uid,ignore_gid)
    return 0

def q_process_file(q,fname,ignore_uid,ignore_gid):
    CHOWN = False
    fstat = os.lstat(fname)
    mode = fstat.st_mode
    uid = fstat.st_uid
    gid = fstat.st_gid

    if ignore_uid:
        new_uid = -1
    else:
        new_uid = checkID('uid',uid)

    if ignore_gid:
        new_gid = -1
    else:
        new_gid = checkID('gid',gid)

    if -2 != (new_uid + new_gid): CHOWN = True

    Print("(uid,gid) = (%d,%d)" % (new_uid,new_gid), verbose=3)
    PrintDebug("uid change: %d -> %d ; gid change: %d -> %d ; %s" % (uid,new_uid,gid,new_gid,fname) , debug=3)

    # The chown is located inside the file checks to ingore block files,
    # character devices, named pipes, and UNIX sockets
    if stat.S_ISDIR(mode):
        if CHOWN: os.chown(fname,new_uid,new_gid)
        q.put(fname)
        return 0

    if stat.S_ISREG(mode):
        if CHOWN: os.chown(fname,new_uid,new_gid)
        return 0

    if stat.S_ISLNK(mode):
        if CHOWN: os.lchown(fname,new_uid,new_gid)
        return 0

def queue_worker(q,ignore_uid,ignore_gid):
    while True:
        try:
            dir_name = q.get()
            q_process_dir(q,dir_name,ignore_uid,ignore_gid)
            q.task_done()
        except:
            break

def main():
    global DEBUG
    global SYMLINK_OVERRIDE
    global VERBOSE

    pvers = "%d.%d.%d"%(__MAJOR__,__MINOR__,__RELEASE__);
    parser = ap.ArgumentParser(
            description = "An application to apply a massive numerical UID/GID change recursively on a directory or set of directories",
            epilog = "An example map file can be printed using the --map-example argument.")

    parser.add_argument("-V","--version",action="version", version="%%(prog)s (%s)"%(pvers))

    parser.add_argument("-v","--verbose",action="count",default=0,help="scalable verbose output (STDOUT)")

    parser.add_argument("-D","--debug",action="count",default=0,help="scalable debugging output (STDERR)")

    parser.add_argument("-d","--dry-run",action="store_true",default=False,
            help="Do a dry run. Scans all the meta-data, but does not call the chown")

    parser.add_argument("-u","--ignore-uid",action="store_true",default=False,
            help="Do NOT change the UID of the files. If used with [-g|--ignore-gid] equal to [-d|--dry-run]")

    parser.add_argument("-g","--ignore-gid",action="store_true",default=False,
            help="Do NOT change the GID of the files. If used with [-u|--ignore-uid] equal to [-d|--dry-run]")
    
    parser.add_argument("-m","--map_file", type=str, default="", help="file describing the UID/GID mapping. See --map-help.")
    
    parser.add_argument("dir", type=str, nargs='*',help="directories to recursively modify permissions")
    
    parser.add_argument("-s","--follow-symlinks",action="store_true",default=False,
            help="Follow symbolic links. WARNING: May cause large overhead and repeat system calls!")

    parser.add_argument("-q","--use-queue",action="store",type=int,default=0,metavar="N",
            help="Use a multiprocessing queue recursion with 'N' processes/threads rather than standard serialized recursion")
   
    parser.add_argument("-U","--usage",action="store_true", default=False, help="Quick overview on how the application works.")

    parser.add_argument("--map-example",action="store_true", default=False, help="Print out a map file example to STDOUT.")

    args = parser.parse_args()

    if args.usage:
        PrintUsage()
        return 0

    if args.map_example:
        PrintMapExample()
        return 0

    DEBUG = args.debug
    PrintDebug("Debugging set at %d" % (DEBUG),debug=1)
    
    SYMLINK_OVERRIDE = args.follow_symlinks
    if args.follow_symlinks:
        PrintWarn("You've chosen to follow symbolic links; Be wary of symbolic link loops!!!")
    
    VERBOSE = args.verbose
    Print("verbose level = %d" % ( args.verbose ), verbose=1 )

    ignore_uid = args.ignore_uid
    ignore_gid = args.ignore_gid

    if args.dry_run is True:
        Print("Running in Dry-run mode")
        ignore_uid=True
        ignore_gid=True
    
    # Generate the UID/GID maps
    PrintDebug("map file is : %s" %(args.map_file),debug=1)
    map_code = GenerateMap(args.map_file)
    if map_code:
        sys.exit(map_code)
    
    if args.use_queue > 0:
        dir_queue = JoinableQueue()

        ppool = Pool(args.use_queue,queue_worker,(dir_queue,ignore_uid,ignore_gid,))

        for each in args.dir:
            dir_name = os.path.abspath(each)
            Print(dir_name,verbose=0)
            q_process_dir(dir_queue,dir_name,ignore_uid,ignore_gid)
            
        dir_queue.join()

    else:
        # Loop over the directory(ies) using serialized recursion
        Print("")
        for each in args.dir:
            WalkDirTree( os.path.abspath(each), lvl=0,ignore_uid=ignore_uid,ignore_gid=ignore_gid)
            Print("")

    return 0

# Run the main app
if __name__ == "__main__": main()
