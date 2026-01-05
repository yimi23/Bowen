#!/usr/bin/env python3
"""
BOWEN Backup Manager
Auto-backup BOWEN memory and knowledge to GitHub
"""

import subprocess
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BackupManager:
    """Auto-backup BOWEN memory to GitHub"""
    
    def __init__(self, bowen_path='/Users/yimi/Desktop/bowen'):
        self.bowen_path = bowen_path
        self.backup_files = [
            'memory.json',
            'knowledge/concepts.json',
            'knowledge/connections.json',
            'knowledge/sources.json',
            'user_context.yaml'
        ]
    
    def init_repo(self):
        """One-time: Initialize git repo and create GitHub repo"""
        os.chdir(self.bowen_path)
        
        commands = [
            'git init',
            'echo "*.pyc\n__pycache__/\n.DS_Store\n*.log\noutlook_token.json" > .gitignore',
            'git add memory.json knowledge/ user_context.yaml .gitignore',
            'git commit -m "Initial BOWEN memory backup"',
            'gh repo create bowen-memory --private --source=. --push || echo "Repo may already exist"'
        ]
        
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0 and 'already exists' not in result.stderr.lower():
                logger.error(f"Git init error: {result.stderr}")
                return False
        
        logger.info("Git repo initialized")
        return True
    
    def backup(self, message=None):
        """Backup current state"""
        os.chdir(self.bowen_path)
        
        if not message:
            message = f"Auto-backup {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Check if git is initialized
        if not os.path.exists('.git'):
            logger.info("Git not initialized, initializing now...")
            self.init_repo()
        
        # Prepare files that exist
        existing_files = []
        for file_path in self.backup_files:
            if os.path.exists(file_path):
                existing_files.append(file_path)
        
        if not existing_files:
            logger.warning("No backup files found")
            return {"success": False, "error": "No files to backup"}
        
        commands = [
            f'git add {" ".join(existing_files)}',
            f'git commit -m "{message}" || echo "Nothing to commit"',
            'git push origin main || git push || echo "Push failed - check remote"'
        ]
        
        success = True
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0 and 'nothing to commit' not in result.stdout.lower():
                logger.warning(f"Command failed: {cmd} - {result.stderr}")
                success = False
        
        if success:
            logger.info(f"Backed up: {message}")
        return {"success": success, "message": message}
    
    def restore(self):
        """Restore from GitHub"""
        os.chdir(self.bowen_path)
        
        result = subprocess.run('git pull', shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Restored from GitHub")
            return {"success": True}
        else:
            logger.error(f"Restore failed: {result.stderr}")
            return {"success": False, "error": result.stderr}
    
    def get_backup_status(self):
        """Get status of backup repo"""
        os.chdir(self.bowen_path)
        
        if not os.path.exists('.git'):
            return {"initialized": False, "message": "Git not initialized"}
        
        # Check for uncommitted changes
        status_result = subprocess.run('git status --porcelain', shell=True, capture_output=True, text=True)
        has_changes = bool(status_result.stdout.strip())
        
        # Get last commit info
        log_result = subprocess.run('git log -1 --pretty=format:"%h %s %cd" --date=short', shell=True, capture_output=True, text=True)
        last_commit = log_result.stdout.strip() if log_result.returncode == 0 else "No commits"
        
        return {
            "initialized": True,
            "has_uncommitted_changes": has_changes,
            "last_commit": last_commit,
            "files_tracked": len([f for f in self.backup_files if os.path.exists(f)])
        }


# Test
if __name__ == "__main__":
    backup = BackupManager()
    
    print("🔍 Checking backup status...")
    status = backup.get_backup_status()
    print(f"Status: {status}")
    
    # Init if needed
    if not status.get("initialized"):
        print("📦 Initializing git repo...")
        backup.init_repo()
    
    # Test backup
    print("💾 Testing backup...")
    result = backup.backup("Test backup from backup_manager.py")
    print(f"Backup result: {result}")
    
    # Show final status
    final_status = backup.get_backup_status()
    print(f"Final status: {final_status}")