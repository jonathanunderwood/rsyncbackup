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

# Number of days to keep backups for. If this is 0, then only the most recent
# backup will be kept. If this is negative, backups will never be deleted.
KEEP_DAYS = 30

import sys
import logging
import backupdir

# Set up basic logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Do the work
budir = backupdir.BackupDir(directory=DEST)
budir.add_new_backup(source=SRC, rsync_options=RSYNC_OPTS)
budir.prune(retension_period_days=KEEP_DAYS)

# Shutdown
logger.info('done')
logging.shutdown()
sys.exit(0)
