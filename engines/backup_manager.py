import subprocess
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BackupManager:
    """Auto-backup BOWEN memory to GitHub"""
    
    def __init__(self, bowen_path='/Users/yimi/Desktop/bowen'):
        self.bowen_path = bowen_path
        self.remote_url = "https://github.com/yimi23/Bowen.git"
        self.backup_files = [
            'memory.json',
            'knowledge/concepts.json',
            'knowledge/connections.json',
            'user_context.yaml'
        ]
    
    def init_repo(self):
        """One-time: Connect to existing GitHub repo"""
        os.chdir(self.bowen_path)
        
        # Check if remote exists
        result = subprocess.run(['git', 'remote', '-v'], 
                              capture_output=True, text=True)
        
        if 'origin' not in result.stdout:
            # Add remote
            subprocess.run(['git', 'remote', 'add', 'origin', self.remote_url],
                         capture_output=True)
            logger.info(f"Connected to {self.remote_url}")
        
        return True
    
    def backup(self, message=None):
        """Backup current state to GitHub"""
        os.chdir(self.bowen_path)
        
        if not message:
            message = f"Auto-backup {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        commands = [
            f'git add {" ".join(self.backup_files)}',
            f'git commit -m "{message}" || echo "Nothing to commit"',
            'git push origin main || git push origin master'
        ]
        
        for cmd in commands:
            subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        logger.info(f"Backed up to GitHub: {message}")
        return {"success": True, "message": message, "repo": self.remote_url}
    
    def restore(self):
        """Restore from GitHub"""
        os.chdir(self.bowen_path)
        
        result = subprocess.run('git pull origin main || git pull origin master', 
                              shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Restored from GitHub")
            return {"success": True}
        else:
            logger.error(f"Restore failed: {result.stderr}")
            return {"success": False, "error": result.stderr}