/*
ogChanger:  Designed to recursively traverse directories
            and map new uid/gid from old uid/gid. This is
            experimental and should not be used without 
            understanding consequences of having an incorrect
            mapping.

Author:     Jared D. Baker <jared.baker@uwyo.edu>
*/

#include <stdlib.h>
#include <stdio.h>
#include <dirent.h>
#include <errno.h>
#include <limits.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>

// GPFS library for later if necessary
// #include <gpfs.h>

int process_file(const char* path);
int process_dir(const char* path);


int process_dir(const char* path){

    char dirA[PATH_MAX + 1];
    char fname[PATH_MAX + 1];
    char rpath[PATH_MAX + 1];
    char* pathsep = "/";

    DIR *dp;
    struct dirent *ep;

    dp = opendir(path);
    if (NULL != dp) {
        while(ep = readdir(dp)) {
            strcpy(fname,ep->d_name);

            if ( (0 < strcmp(fname,".")) && (0 < strcmp(fname,"..")) ) {
                // Get the absolute path name to avoid recursive lookup issues
                strcpy(rpath,path);
                strcat(rpath,pathsep);
                strcat(rpath,fname);
                // Process Each File
                process_file(rpath);
            }
        }
        (void)closedir(dp);
    }
    else {
        fprintf(stderr,"Can't open: %s\n",path);
        return 1;
    }

    return 0;
}

int process_file(const char* path){
    int rc = 0;
    int statrc;
    struct stat fname_st;
    mode_t mode;
    uid_t uid;
    gid_t gid;
    
    statrc = lstat(path,&fname_st);
    mode = fname_st.st_mode;
    uid  = fname_st.st_uid;
    gid  = fname_st.st_gid;

    if S_ISDIR(mode) {
        printf("(%c,%u,%u) %s\n",'d',uid,gid,path);
        // Recurse into other directories
        //printf("Please recurse further...\n");
        rc = process_dir(path);
    }
    else if S_ISREG(mode) {
        printf("(%c,%u,%u) %s\n",'-',uid,gid,path);
    }

    return rc;
}

int main( int argc, char* argv[] ) {
    int rc;
    char path[PATH_MAX+1];
    // Transform the original directory into absolute path:
    realpath(argv[1],path);
    printf("Aboslute Path Starting: %s\n\n",path);
    rc = process_dir(path);
    return rc;
}
