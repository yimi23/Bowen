#!/usr/bin/env python3
"""
BOWEN Intelligent File Management Engine
Organizes, cleans, and manages files intelligently
"""

import os
import shutil
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import json

logger = logging.getLogger(__name__)

class IntelligentFileManager:
    """
    Intelligent file management system that:
    1. Smart file organization by type, project, date
    2. Duplicate detection and removal
    3. Project structure creation
    4. Automated file cleanup
    5. Backup management
    """
    
    def __init__(self, workspace: str = "/Users/yimi/Desktop"):
        """Initialize with workspace directory"""
        self.workspace = Path(workspace)
        
        # File type categories
        self.file_categories = {
            "code": [
                ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss", ".sass",
                ".java", ".cpp", ".c", ".h", ".swift", ".kt", ".go", ".rs", ".php",
                ".rb", ".sh", ".bat", ".ps1", ".sql", ".json", ".xml", ".yaml", ".yml"
            ],
            "documents": [
                ".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt",
                ".xls", ".xlsx", ".csv", ".ppt", ".pptx", ".odp"
            ],
            "media": [
                ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp", ".tiff", ".webp",
                ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".flac", ".aac"
            ],
            "archives": [
                ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"
            ],
            "config": [
                ".env", ".gitignore", ".eslintrc", ".prettierrc", ".babelrc",
                ".dockerfile", "dockerfile", ".ini", ".conf", ".config"
            ],
            "data": [
                ".db", ".sqlite", ".sqlite3", ".json", ".csv", ".tsv", ".parquet"
            ]
        }
        
        # Project indicators
        self.project_indicators = {
            "react": ["package.json", "src/", "public/", "node_modules/"],
            "python": ["requirements.txt", "setup.py", "__pycache__/", ".py"],
            "node": ["package.json", "node_modules/", ".js"],
            "git": [".git/"],
            "docker": ["Dockerfile", "docker-compose.yml"],
            "next": ["next.config.js", "pages/", "app/"],
            "vue": ["vue.config.js", "src/components/"],
            "flutter": ["pubspec.yaml", "lib/", "android/", "ios/"]
        }
        
        logger.info(f"File Manager initialized for workspace: {self.workspace}")
    
    def organize_directory(self, path: str, rules: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Organize files by type, project, date, or custom rules
        """
        try:
            target_path = Path(path)
            if not target_path.exists():
                return {"success": False, "error": f"Path does not exist: {path}"}
            
            rules = rules or {}
            group_by = rules.get("group_by", "type")  # type, project, date
            create_folders = rules.get("create_folders", True)
            remove_duplicates = rules.get("remove_duplicates", False)
            
            logger.info(f"Organizing directory: {path} by {group_by}")
            
            # Scan directory
            files_info = self._scan_directory(target_path)
            
            # Remove duplicates if requested
            if remove_duplicates:
                duplicates = self.find_duplicates(path)
                self._remove_duplicates(duplicates)
            
            # Organize based on grouping method
            if group_by == "type":
                result = self._organize_by_type(target_path, files_info, create_folders)
            elif group_by == "project":
                result = self._organize_by_project(target_path, files_info, create_folders)
            elif group_by == "date":
                result = self._organize_by_date(target_path, files_info, create_folders)
            else:
                result = self._organize_custom(target_path, files_info, rules)
            
            return {
                "success": True,
                "organized_files": result["moved_files"],
                "created_directories": result["created_dirs"],
                "summary": result["summary"]
            }
            
        except Exception as e:
            logger.error(f"Error organizing directory: {e}")
            return {"success": False, "error": str(e)}
    
    def find_duplicates(self, path: str) -> List[Tuple[str, List[str]]]:
        """
        Find duplicate files by comparing file hashes
        Returns list of (hash, [file_paths]) tuples
        """
        try:
            target_path = Path(path)
            file_hashes = {}
            
            logger.info(f"Scanning for duplicates in: {path}")
            
            # Calculate hashes for all files
            for file_path in target_path.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    try:
                        file_hash = self._calculate_file_hash(file_path)
                        if file_hash not in file_hashes:
                            file_hashes[file_hash] = []
                        file_hashes[file_hash].append(str(file_path))
                    except Exception as e:
                        logger.warning(f"Could not hash file {file_path}: {e}")
                        continue
            
            # Find duplicates
            duplicates = [(hash_val, files) for hash_val, files in file_hashes.items() if len(files) > 1]
            
            logger.info(f"Found {len(duplicates)} sets of duplicate files")
            return duplicates
            
        except Exception as e:
            logger.error(f"Error finding duplicates: {e}")
            return []
    
    def create_project_structure(self, project_type: str, path: str, name: str = None) -> str:
        """
        Create standard project structure for different project types
        """
        try:
            project_path = Path(path)
            if name:
                project_path = project_path / name
            
            project_path.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Creating {project_type} project structure at: {project_path}")
            
            if project_type == "react":
                self._create_react_structure(project_path)
            elif project_type == "python":
                self._create_python_structure(project_path)
            elif project_type == "node":
                self._create_node_structure(project_path)
            elif project_type == "generic":
                self._create_generic_structure(project_path)
            else:
                raise ValueError(f"Unknown project type: {project_type}")
            
            return str(project_path)
            
        except Exception as e:
            logger.error(f"Error creating project structure: {e}")
            return f"Error: {str(e)}"
    
    def cleanup_workspace(self, path: str, aggressive: bool = False) -> Dict[str, Any]:
        """
        Clean up directory by removing temporary files, caches, etc.
        """
        try:
            target_path = Path(path)
            cleaned_items = []
            space_freed = 0
            
            logger.info(f"Cleaning workspace: {path} (aggressive: {aggressive})")
            
            # Define cleanup patterns
            cleanup_patterns = {
                "temp_files": ["*.tmp", "*.temp", "*~", "*.bak", "*.swp"],
                "cache_dirs": ["__pycache__", ".pytest_cache", "node_modules", ".cache", "cache"],
                "build_artifacts": ["dist", "build", "*.pyc", "*.pyo", "*.class"],
                "log_files": ["*.log", "*.log.*"],
                "os_files": [".DS_Store", "Thumbs.db", "desktop.ini"]
            }
            
            if aggressive:
                cleanup_patterns.update({
                    "backup_files": ["*.backup", "*.old", "*_backup", "*_old"],
                    "temp_dirs": ["tmp", "temp", "temporary"]
                })
            
            # Clean based on patterns
            for category, patterns in cleanup_patterns.items():
                for pattern in patterns:
                    for item in target_path.rglob(pattern):
                        try:
                            size = self._get_size(item)
                            if item.is_file():
                                item.unlink()
                            elif item.is_dir():
                                shutil.rmtree(item)
                            
                            cleaned_items.append({
                                "path": str(item),
                                "type": category,
                                "size": size
                            })
                            space_freed += size
                            
                        except Exception as e:
                            logger.warning(f"Could not clean {item}: {e}")
            
            # Clean empty directories
            self._remove_empty_directories(target_path)
            
            return {
                "success": True,
                "cleaned_items": len(cleaned_items),
                "space_freed_mb": round(space_freed / (1024 * 1024), 2),
                "details": cleaned_items
            }
            
        except Exception as e:
            logger.error(f"Error cleaning workspace: {e}")
            return {"success": False, "error": str(e)}
    
    def create_backup(self, source_path: str, backup_name: str = None) -> str:
        """
        Create backup of directory or file
        """
        try:
            source = Path(source_path)
            if not source.exists():
                raise ValueError(f"Source path does not exist: {source_path}")
            
            # Create backup directory
            backup_dir = self.workspace / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            # Generate backup name
            if not backup_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"{source.name}_backup_{timestamp}"
            
            backup_path = backup_dir / backup_name
            
            logger.info(f"Creating backup: {source} -> {backup_path}")
            
            if source.is_file():
                shutil.copy2(source, backup_path)
            else:
                shutil.copytree(source, backup_path)
            
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return f"Error: {str(e)}"
    
    def _scan_directory(self, path: Path) -> Dict[str, Any]:
        """Scan directory and collect file information"""
        files_info = {
            "total_files": 0,
            "total_size": 0,
            "file_types": {},
            "projects_detected": [],
            "files_by_category": {}
        }
        
        # Scan all files
        for file_path in path.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                files_info["total_files"] += 1
                
                # File size
                try:
                    size = file_path.stat().st_size
                    files_info["total_size"] += size
                except:
                    size = 0
                
                # File extension
                ext = file_path.suffix.lower()
                if ext not in files_info["file_types"]:
                    files_info["file_types"][ext] = {"count": 0, "size": 0}
                files_info["file_types"][ext]["count"] += 1
                files_info["file_types"][ext]["size"] += size
                
                # Category
                category = self._get_file_category(ext)
                if category not in files_info["files_by_category"]:
                    files_info["files_by_category"][category] = []
                files_info["files_by_category"][category].append(file_path)
        
        # Detect project types
        files_info["projects_detected"] = self._detect_projects(path)
        
        return files_info
    
    def _organize_by_type(self, path: Path, files_info: Dict[str, Any], create_folders: bool) -> Dict[str, Any]:
        """Organize files by file type/category"""
        moved_files = 0
        created_dirs = []
        
        for category, files in files_info["files_by_category"].items():
            if not files or category == "unknown":
                continue
            
            if create_folders:
                category_dir = path / f"organized_{category}"
                if not category_dir.exists():
                    category_dir.mkdir()
                    created_dirs.append(str(category_dir))
                
                # Move files
                for file_path in files:
                    try:
                        new_path = category_dir / file_path.name
                        # Handle name conflicts
                        counter = 1
                        while new_path.exists():
                            name_parts = file_path.stem, counter, file_path.suffix
                            new_path = category_dir / f"{name_parts[0]}_{name_parts[1]}{name_parts[2]}"
                            counter += 1
                        
                        shutil.move(str(file_path), str(new_path))
                        moved_files += 1
                    except Exception as e:
                        logger.warning(f"Could not move {file_path}: {e}")
        
        return {
            "moved_files": moved_files,
            "created_dirs": created_dirs,
            "summary": f"Organized {moved_files} files into {len(created_dirs)} categories"
        }
    
    def _organize_by_project(self, path: Path, files_info: Dict[str, Any], create_folders: bool) -> Dict[str, Any]:
        """Organize files by detected project types"""
        moved_files = 0
        created_dirs = []
        
        projects = files_info["projects_detected"]
        if not projects:
            return self._organize_by_type(path, files_info, create_folders)
        
        for project_type in projects:
            if create_folders:
                project_dir = path / f"projects_{project_type}"
                if not project_dir.exists():
                    project_dir.mkdir()
                    created_dirs.append(str(project_dir))
                
                # Move project-related files
                for file_path in path.iterdir():
                    if file_path.is_file() and self._is_project_file(file_path, project_type):
                        try:
                            new_path = project_dir / file_path.name
                            if not new_path.exists():
                                shutil.move(str(file_path), str(new_path))
                                moved_files += 1
                        except Exception as e:
                            logger.warning(f"Could not move {file_path}: {e}")
        
        return {
            "moved_files": moved_files,
            "created_dirs": created_dirs,
            "summary": f"Organized {moved_files} files by project type"
        }
    
    def _organize_by_date(self, path: Path, files_info: Dict[str, Any], create_folders: bool) -> Dict[str, Any]:
        """Organize files by modification date"""
        moved_files = 0
        created_dirs = []
        
        # Group files by month
        date_groups = {}
        for category, files in files_info["files_by_category"].items():
            for file_path in files:
                try:
                    mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    month_key = mod_time.strftime("%Y-%m")
                    
                    if month_key not in date_groups:
                        date_groups[month_key] = []
                    date_groups[month_key].append(file_path)
                except:
                    continue
        
        # Create directories and move files
        if create_folders:
            for month_key, files in date_groups.items():
                date_dir = path / f"by_date_{month_key}"
                if not date_dir.exists():
                    date_dir.mkdir()
                    created_dirs.append(str(date_dir))
                
                for file_path in files:
                    try:
                        new_path = date_dir / file_path.name
                        if not new_path.exists():
                            shutil.move(str(file_path), str(new_path))
                            moved_files += 1
                    except Exception as e:
                        logger.warning(f"Could not move {file_path}: {e}")
        
        return {
            "moved_files": moved_files,
            "created_dirs": created_dirs,
            "summary": f"Organized {moved_files} files by date"
        }
    
    def _organize_custom(self, path: Path, files_info: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
        """Organize files using custom rules"""
        # Implement custom organization logic based on rules
        return {
            "moved_files": 0,
            "created_dirs": [],
            "summary": "Custom organization completed"
        }
    
    def _get_file_category(self, extension: str) -> str:
        """Get category for file extension"""
        extension = extension.lower()
        for category, extensions in self.file_categories.items():
            if extension in extensions:
                return category
        return "unknown"
    
    def _detect_projects(self, path: Path) -> List[str]:
        """Detect project types in directory"""
        detected = []
        
        for project_type, indicators in self.project_indicators.items():
            for indicator in indicators:
                if indicator.endswith('/'):
                    # Directory indicator
                    if (path / indicator.rstrip('/')).exists():
                        detected.append(project_type)
                        break
                else:
                    # File indicator
                    if (path / indicator).exists() or list(path.glob(f"*{indicator}")):
                        detected.append(project_type)
                        break
        
        return detected
    
    def _is_project_file(self, file_path: Path, project_type: str) -> bool:
        """Check if file belongs to specific project type"""
        ext = file_path.suffix.lower()
        indicators = self.project_indicators.get(project_type, [])
        
        for indicator in indicators:
            if indicator.startswith('.'):
                if ext == indicator:
                    return True
            elif indicator in file_path.name:
                return True
        
        return False
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _remove_duplicates(self, duplicates: List[Tuple[str, List[str]]]):
        """Remove duplicate files, keeping the first one"""
        for hash_val, file_paths in duplicates:
            # Keep the first file, remove the rest
            for file_path in file_paths[1:]:
                try:
                    Path(file_path).unlink()
                    logger.info(f"Removed duplicate: {file_path}")
                except Exception as e:
                    logger.warning(f"Could not remove duplicate {file_path}: {e}")
    
    def _get_size(self, path: Path) -> int:
        """Get size of file or directory in bytes"""
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        return 0
    
    def _remove_empty_directories(self, path: Path):
        """Remove empty directories recursively"""
        for dir_path in path.rglob('*'):
            if dir_path.is_dir():
                try:
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        logger.info(f"Removed empty directory: {dir_path}")
                except:
                    continue
    
    def _create_react_structure(self, project_path: Path):
        """Create React project structure"""
        dirs = ["src", "src/components", "src/styles", "src/utils", "public", "tests"]
        files = {
            "src/App.js": "// React App component",
            "src/index.js": "// React entry point",
            "public/index.html": "<!DOCTYPE html><html><head><title>React App</title></head><body><div id=\"root\"></div></body></html>",
            "package.json": '{"name": "react-app", "version": "1.0.0"}',
            "README.md": "# React Application"
        }
        
        self._create_structure(project_path, dirs, files)
    
    def _create_python_structure(self, project_path: Path):
        """Create Python project structure"""
        dirs = ["src", "tests", "docs", "scripts"]
        files = {
            "src/__init__.py": "",
            "tests/__init__.py": "",
            "requirements.txt": "# Python dependencies",
            "setup.py": "# Python setup configuration",
            "README.md": "# Python Project",
            ".gitignore": "__pycache__/\n*.pyc\n*.pyo\n"
        }
        
        self._create_structure(project_path, dirs, files)
    
    def _create_node_structure(self, project_path: Path):
        """Create Node.js project structure"""
        dirs = ["src", "test", "lib", "bin"]
        files = {
            "src/index.js": "// Node.js entry point",
            "package.json": '{"name": "node-app", "version": "1.0.0", "main": "src/index.js"}',
            "README.md": "# Node.js Application",
            ".gitignore": "node_modules/\n*.log\n"
        }
        
        self._create_structure(project_path, dirs, files)
    
    def _create_generic_structure(self, project_path: Path):
        """Create generic project structure"""
        dirs = ["src", "tests", "docs", "scripts", "assets"]
        files = {
            "README.md": f"# {project_path.name}\n\nProject description here.",
            "LICENSE": "MIT License",
            ".gitignore": "*.log\n*.tmp\n"
        }
        
        self._create_structure(project_path, dirs, files)
    
    def _create_structure(self, project_path: Path, dirs: List[str], files: Dict[str, str]):
        """Helper to create directories and files"""
        # Create directories
        for dir_name in dirs:
            (project_path / dir_name).mkdir(parents=True, exist_ok=True)
        
        # Create files
        for file_path, content in files.items():
            file_full_path = project_path / file_path
            file_full_path.parent.mkdir(parents=True, exist_ok=True)
            file_full_path.write_text(content)
    
    def get_workspace_stats(self) -> Dict[str, Any]:
        """Get statistics about the workspace"""
        try:
            stats = {
                "total_files": 0,
                "total_size_mb": 0,
                "file_types": {},
                "largest_files": [],
                "projects_detected": [],
                "potential_duplicates": 0
            }
            
            # Scan workspace
            for file_path in self.workspace.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    stats["total_files"] += 1
                    
                    try:
                        size = file_path.stat().st_size
                        stats["total_size_mb"] += size
                        
                        ext = file_path.suffix.lower()
                        if ext not in stats["file_types"]:
                            stats["file_types"][ext] = 0
                        stats["file_types"][ext] += 1
                        
                        # Track large files (> 10MB)
                        if size > 10 * 1024 * 1024:
                            stats["largest_files"].append({
                                "path": str(file_path),
                                "size_mb": round(size / (1024 * 1024), 2)
                            })
                    except:
                        continue
            
            # Convert total size to MB
            stats["total_size_mb"] = round(stats["total_size_mb"] / (1024 * 1024), 2)
            
            # Sort largest files
            stats["largest_files"] = sorted(
                stats["largest_files"], 
                key=lambda x: x["size_mb"], 
                reverse=True
            )[:10]
            
            # Detect projects
            stats["projects_detected"] = self._detect_projects(self.workspace)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting workspace stats: {e}")
            return {"error": str(e)}