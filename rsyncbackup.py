#!/usr/bin/python

# TODO: remove the saving state with current symlink stuff and automatically
# establish most recent backup from dates

SRC = './a'
DEST = './b'

# Options passed to rsync
RSYNC_OPTS = ['--archive', 
              '--hard-links', 
              '--acls', 
              '--xattrs', 
              '--fuzzy', 
              '--relative',
              '--verbose', 
              '--delete']

# Number of times to retry the rsync command before giving up
RETRIES = 10

# Format of time stamp used for backup directory naming
TIME_STAMP = '%Y-%m-%d-%H:%M:%S'

# Number of days to keep backups for. If this is 0, then only the most recent
# backup will be kept. If this is negative, backups will never be deleted.
KEEP_DAYS = 30

# If this is set to True, we'll use the logger system to control where output
# goes. Otherwise use stdout, stderr etc.
USE_LOGGER = True

import datetime
import os
import shutil
import sys
import subprocess
import logging
import fnmatch 

# Set up basic logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('rsyncbackup')

# Make the backup directory if not already present - should only occur on
# first backup
if not os.path.isdir(DEST):
    os.mkdir(DEST)

now = datetime.datetime.utcnow()
nowdir = now.strftime(TIME_STAMP)

# Each backup is created in a directory whose name is the time stamp of the
# backup
dest = os.path.join(DEST, nowdir)

# 'current' is a symlink which points to the most recent backup directory
# If the current symlink is present, hard link unchanged files in new backup
# to the previous backup to save space. If not, we'll create a new full
# backup. 
symlink = os.path.join(DEST, 'current')

# Options passed to rsync - see documentation for subprocess.Popen.
rsync_cmd = ['rsync'] + RSYNC_OPTS

if os.path.islink(symlink) and os.path.exists(symlink):
    rsync_cmd += ['--link-dest', os.path.abspath(symlink)]
else:
    logger.info('current symlink not present at destination')

rsync_cmd += [SRC, dest]

# Open log file for rsync output
logfilename = os.path.join(DEST, nowdir + '.log')
logfile = open(logfilename, 'w')

# Retry the rsync command if it fails a number of times before giving up
logger.info('running command: {0}'.format(subprocess.list2cmdline(rsync_cmd)))

for attempt in xrange(RETRIES):
    logfile.write('=' * 30 + '\n')
    logfile.write('rsync attempt {0}\n'.format(attempt))
    logfile.write('=' * 30 + '\n')
    logfile.flush()

    proc = subprocess.Popen(rsync_cmd, close_fds=True, 
                            stdout=logfile,
                            stderr=subprocess.STDOUT)

    # Call communicate() to get the output without blocking, and also set the
    # returncode attribute
    #output, error = proc.communicate()
    # for line in output:
    #     logfile.write(line)

    # Need to call this to ensure that proc.returncode is set. Not that
    # proc.wait() also returns the returncode
    ret = proc.wait()
    if ret:
        success = False
    else:
        success = True

    if success is False:
        logger.error('attempt {0}: rsync failed to complete'.format(attempt))
        logger.error('attempt {0}: rsync return code {1}'.format(attempt, proc.returncode))

        if attempt == RETRIES - 1:
            logger.error('attempt {0}:giving up - backup failed'.format(attempt))
            
                #TODO: at this point we need to decide what to do with the
                #incomplete backup. Currently we don't point current at it. Should
                #we delete it?
    else:
        logger.info('attempt {0}: rsync completed successfully'.format(attempt))
        break

logfile.close()
logger.info('logging all rsync output to {0}'.format(logfilename))

if success is False:
    logging.shutdown()
    sys.exit(1)

# Make the current symlink point to the most recent backup
if os.path.islink(symlink):
    os.remove(symlink)
    make_symlink = True
elif not os.path.exists(symlink):
    make_symlink = True
else:
    print 'not removing current as not a symbolic link'
    make_symlink = False

if make_symlink:
    os.symlink(os.path.basename(dest), os.path.abspath(symlink))
    logger.info('current symlink created and pointing to {0}'.format(dest))

# Prune old backups
if KEEP_DAYS >= 0:
    delta = datetime.timedelta(KEEP_DAYS)
    ls = os.listdir(DEST)

    logs = fnmatch.filter(ls, '*.log')

    for entry in logs:
        entrypath = os.path.join(DEST, entry)
        root, ext = os.path.splitext(entry)
        
        if root is not nowdir:
            try:
                oldtime = datetime.datetime.strptime(root, TIME_STAMP)
            except ValueError:
                logger.info('not removing {0}: not recognized'.format(entrypath))
                continue

            age = now - oldtime
            if age >= delta:
                logger.info('removing old log {0} ({1} days old)'.format(entry, age.days))
                os.remove(entrypath)
                
    nonlogs = [entry for entry in ls if entry not in logs]            

    for entry in nonlogs:
        entrypath = os.path.join(DEST, entry)

        if os.path.isdir(entrypath) and entry not in (nowdir, 'current'):
            try:
                oldtime = datetime.datetime.strptime(entry, TIME_STAMP)
            except ValueError:
                logger.info('skipping {0} as not a backup directory'.format(entry))
                continue

            age = now - oldtime
            if age >= delta:
                logger.info('removing old backup {0} ({1} days old)'.format(entry, age.days))
                shutil.rmtree(entrypath)

logger.info('done')
logging.shutdown()
