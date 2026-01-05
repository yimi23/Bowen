#!/usr/bin/env python3
"""
BOWEN Framework Computer Tools
Enables TAMARA to actually DO workflow automation, not just talk about it
"""

import os
import subprocess
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class ComputerTools:
    """
    Real computer automation tools for TAMARA personality
    Enables actual workflow automation and system integration
    """
    
    def __init__(self, safe_mode: bool = None):
        if safe_mode is None:
            safe_mode = os.getenv('TAMARA_SAFE_MODE', 'true').lower() == 'true'
        
        self.safe_mode = safe_mode
        
        # Get allowed directories from environment or use defaults
        env_dirs = os.getenv('TAMARA_ALLOWED_DIRS')
        if env_dirs:
            self.allowed_directories = [d.strip() for d in env_dirs.split(',')]
        else:
            self.allowed_directories = [
                "/Users/yimi/Desktop",
                "/tmp",
                "/var/folders",  # macOS temp directories
                str(Path.home() / "Documents"),
                str(Path.home() / "Downloads"),
                str(Path.home() / "Desktop")
            ]
        
    def is_path_safe(self, path: str) -> bool:
        """Check if path is in allowed directories for safe operation"""
        if not self.safe_mode:
            return True
            
        abs_path = os.path.abspath(path)
        return any(abs_path.startswith(allowed) for allowed in self.allowed_directories)
    
    def bash_tool(self, command: str, working_dir: str = None) -> Dict[str, Any]:
        """Execute bash commands safely"""
        try:
            if working_dir and not self.is_path_safe(working_dir):
                return {
                    "success": False,
                    "error": f"Directory {working_dir} not in allowed paths",
                    "output": ""
                }
            
            # Safety restrictions
            dangerous_commands = ['rm -rf', 'sudo', 'chmod +x', 'curl', 'wget']
            if any(dangerous in command for dangerous in dangerous_commands):
                if self.safe_mode:
                    return {
                        "success": False,
                        "error": f"Command blocked for safety: {command}",
                        "output": ""
                    }
            
            # Execute command
            timeout = int(os.getenv('BASH_TIMEOUT', '30'))
            
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds",
                "output": ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": ""
            }
    
    def create_file(self, path: str, content: str) -> Dict[str, Any]:
        """Create a new file with content"""
        try:
            if not self.is_path_safe(path):
                return {
                    "success": False,
                    "error": f"Path {path} not in allowed directories"
                }
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Write file
            with open(path, 'w') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"File created successfully: {path}",
                "path": path,
                "size": len(content)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def read_file(self, path: str) -> Dict[str, Any]:
        """Read file content"""
        try:
            if not self.is_path_safe(path):
                return {
                    "success": False,
                    "error": f"Path {path} not in allowed directories"
                }
            
            with open(path, 'r') as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content,
                "path": path,
                "size": len(content)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def str_replace(self, path: str, old_str: str, new_str: str) -> Dict[str, Any]:
        """Replace string in file (like Claude's str_replace tool)"""
        try:
            if not self.is_path_safe(path):
                return {
                    "success": False,
                    "error": f"Path {path} not in allowed directories"
                }
            
            # Read current content
            with open(path, 'r') as f:
                content = f.read()
            
            # Check if old_str exists
            if old_str not in content:
                return {
                    "success": False,
                    "error": f"String not found in file: {old_str}"
                }
            
            # Replace string
            new_content = content.replace(old_str, new_str)
            
            # Write back
            with open(path, 'w') as f:
                f.write(new_content)
            
            return {
                "success": True,
                "message": f"String replaced in {path}",
                "old_str": old_str,
                "new_str": new_str,
                "path": path
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_files(self, directory: str) -> Dict[str, Any]:
        """List files in directory"""
        try:
            if not self.is_path_safe(directory):
                return {
                    "success": False,
                    "error": f"Directory {directory} not in allowed paths"
                }
            
            files = []
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                files.append({
                    "name": item,
                    "type": "file" if os.path.isfile(item_path) else "directory",
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None
                })
            
            return {
                "success": True,
                "files": files,
                "directory": directory,
                "count": len(files)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_workflow_automation(self, workflow_name: str, steps: List[str], output_dir: str) -> Dict[str, Any]:
        """Create automated workflow script"""
        try:
            if not self.is_path_safe(output_dir):
                return {
                    "success": False,
                    "error": f"Output directory {output_dir} not in allowed paths"
                }
            
            # Create workflow script
            script_content = f"""#!/bin/bash
# BOWEN Framework Workflow: {workflow_name}
# Generated by TAMARA personality
# Created: {os.popen('date').read().strip()}

echo "🌟 Starting workflow: {workflow_name}"

"""
            
            for i, step in enumerate(steps, 1):
                script_content += f"""
echo "Step {i}: {step}"
{step}
if [ $? -ne 0 ]; then
    echo "❌ Step {i} failed: {step}"
    exit 1
fi
"""
            
            script_content += f"""
echo "✅ Workflow completed successfully: {workflow_name}"
"""
            
            # Write script file
            script_path = os.path.join(output_dir, f"{workflow_name.replace(' ', '_').lower()}_workflow.sh")
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Make executable
            os.chmod(script_path, 0o755)
            
            return {
                "success": True,
                "message": f"Workflow automation created: {workflow_name}",
                "script_path": script_path,
                "steps": len(steps)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_optimization_report(self, process_name: str, metrics: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
        """Generate process optimization report"""
        try:
            if not self.is_path_safe(output_dir):
                return {
                    "success": False,
                    "error": f"Output directory {output_dir} not in allowed paths"
                }
            
            # Create report
            report = {
                "process_name": process_name,
                "analysis_date": os.popen('date').read().strip(),
                "metrics": metrics,
                "recommendations": [],
                "automation_opportunities": []
            }
            
            # Add recommendations based on metrics
            if "time_spent" in metrics and metrics["time_spent"] > 60:
                report["recommendations"].append("Consider automation for time-consuming tasks")
                report["automation_opportunities"].append("Create bash script for repetitive steps")
            
            if "error_rate" in metrics and metrics["error_rate"] > 0.1:
                report["recommendations"].append("Add validation checks to reduce errors")
                report["automation_opportunities"].append("Implement input validation")
            
            if "manual_steps" in metrics and metrics["manual_steps"] > 5:
                report["recommendations"].append("Break down into smaller automated components")
                report["automation_opportunities"].append("Create modular workflow scripts")
            
            # Write report file
            report_path = os.path.join(output_dir, f"{process_name.replace(' ', '_').lower()}_optimization_report.json")
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            return {
                "success": True,
                "message": f"Process optimization report created for: {process_name}",
                "report_path": report_path,
                "recommendations": len(report["recommendations"])
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

class TAMARAToolRegistry:
    """
    Tool registry specifically for TAMARA personality
    Maps TAMARA's capabilities to actual computer tools
    """
    
    def __init__(self, safe_mode: bool = True):
        self.tools = ComputerTools(safe_mode)
        self.tool_descriptions = {
            "bash_tool": "Execute bash commands for system automation",
            "create_file": "Create new files with specified content",
            "str_replace": "Edit files by replacing specific strings",
            "read_file": "Read and analyze file contents",
            "list_files": "List and organize directory contents",
            "create_workflow_automation": "Generate automated workflow scripts",
            "process_optimization_report": "Analyze and optimize business processes"
        }
    
    def get_available_tools(self) -> List[str]:
        """Get list of tools available to TAMARA"""
        return list(self.tool_descriptions.keys())
    
    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool by name with parameters"""
        if tool_name not in self.tool_descriptions:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
        
        try:
            tool_method = getattr(self.tools, tool_name)
            return tool_method(**kwargs)
        except Exception as e:
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}"
            }
    
    def format_tool_result(self, tool_name: str, result: Dict[str, Any], for_user: bool = True) -> str:
        """Format tool execution result for display"""
        if not for_user:
            return json.dumps(result, indent=2)
        
        if result["success"]:
            if tool_name == "create_file":
                return f"✅ File created successfully: {result['path']} ({result['size']} characters)"
            elif tool_name == "bash_tool":
                return f"✅ Command executed successfully:\n{result['output']}"
            elif tool_name == "str_replace":
                return f"✅ File updated: {result['path']}"
            elif tool_name == "create_workflow_automation":
                return f"✅ Workflow automation created: {result['script_path']} with {result['steps']} steps"
            elif tool_name == "process_optimization_report":
                return f"✅ Optimization report created: {result['report_path']} with {result['recommendations']} recommendations"
            else:
                return f"✅ {tool_name} completed successfully"
        else:
            return f"❌ {tool_name} failed: {result['error']}"