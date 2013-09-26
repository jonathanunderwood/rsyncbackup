import datetime
import os
import shutil
import sys
import subprocess
import logging
import fnmatch 

class BackupDir():
    directory = None
    time_stamp_format = None
    backup_dict = None
    logger = None

    def __init__ (self, directory, time_stamp_format = '%Y-%m-%d-%H:%M:%S'):
        self.directory = os.path.abspath(directory)
        self.time_stamp_format = time_stamp_format
        self.backups = dict()
        
        # Create backup directory if it's not already present
        if not os.path.isdir(directory):
            os.mkdir(directory)
            
        # Populate dictionary of previous backups if present
        ls = os.listdir(directory)
        dirs = [entry for entry in ls if os.path.isdir(os.path.join(directory, entry))]
        if len(dirs) > 0:
            for entry in dirs:
                try:
                    dt = datetime.datetime.strptime(entry, self.time_stamp_format)
                    self.backups[entry] = dt
                except ValueError:
                    # Entry does not appear to be a backup directory, so skip
                    continue
        # Set up logging
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)

    def __len__(self):
        return len(self.backup_dict)

    def most_recent_backup(self):
        if len(self.backups):
            list = sorted(self.backups, key=self.backups.get, reverse=True)
            return list[0]
        else:
            return None

    def prune(self, retension_period_days):
        delta = datetime.timedelta(retension_period_days)
        now = datetime.datetime.utcnow()
        for bu in self.backups:
            age = now - self.backups[bu]
            if age > delta:
                # remove the backup
                shutil.rmtree(os.path.join(self.directory, bu))
                # remove related log file 
                logfile = bu + '.log'
                os.remove (os.path.join(self.directory, logfile))
                # remove entry from dictionary
                del self.backups[bu]
    
    def add_new_backup(self, source, rsync_options = None):
        '''Add a new backup of source to the directory.'''
        if rsync_options == None:
            rsync_options = ['--archive',
                             '--hard-links',
                             '--acls',
                             '--xattrs',
                             '--fuzzy',
                             '--relative',
                             '--verbose',
                             '--delete']

        rsync_cmd = ['rsync'] + rsync_options

        # If older backups exist in the destination directory, we'll hardlink
        # unchanged files against that
        if len(self.backups):
            rsync_cmd += ['--link-dest', os.path.join(self.directory, self.most_recent_backup())]
        
        # Create path of directory for new backup
        now = datetime.datetime.utcnow()
        nowdir = now.strftime(self.time_stamp_format)
        dest = os.path.join(self.directory, nowdir)
        try:
            os.mkdir(dest)
        except: 
            raise IOError

        rsync_cmd += [os.path.abspath(source), dest]

        # Open log file for rsync output
        logfilename = os.path.join(self.directory, nowdir, nowdir + '.log')
        logfile = open(logfilename, 'w')
        
        # Retry the rsync command if it fails a number of times before giving up
        self.logger.info('running command: {0}'.format(subprocess.list2cmdline(rsync_cmd)))

        proc = subprocess.Popen(rsync_cmd, close_fds=True, 
                                stdout=logfile,
                                stderr=subprocess.STDOUT)

        # Need to call this to ensure that proc.returncode is set. Note that
        # proc.wait() also returns the returncode of the command run.
        if proc.wait(): # command failed to complete
            self.logger.error('rsync failed to complete'.format(attempt))
            self.logger.error('rsync return code {1}'.format(attempt, proc.returncode))
            self.logger.info('logging all rsync output to {0}'.format(logfilename))
            logfile.close()                
            # TODO: at this point we need to decide what to do with
            # the incomplete backup. Should we delete it?  The problem
            # with not deleting it is that subsequent backups will try
            # and hardlink against an incomplete backup, and so waste
            # disk space. We could append "-failed" to the directory
            # name and check for that. Or we could run something like
            # hardlink routinely to recover diskspace.
            os.rename(dest, dest + '-FAILED')
            raise IOError
        else:
            self.logger.info('rsync completed successfully')
            self.logger.info('logging all rsync output to {0}'.format(logfilename))
            logfile.close()
            self.backups[nowdir] = datetime.datetime.strptime(nowdir, self.time_stamp_format)
            return 0

        
