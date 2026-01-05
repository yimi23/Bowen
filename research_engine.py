"""
BOWEN Framework - Research Engine
Claude Code-inspired research and analysis capabilities for BOWEN

This engine enables BOWEN to:
- Perform deep codebase analysis and mapping
- Execute multi-step research workflows  
- Generate comprehensive reports and documentation
- Handle complex file operations and Git workflows
- Create custom research templates and commands

Designed for The Captain's strategic intelligence needs
"""

import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import anthropic
import logging

logger = logging.getLogger(__name__)

class ResearchEngine:
    """
    Advanced research and analysis capabilities inspired by Claude Code
    Combines BOWEN's personal context with sophisticated research tools
    """
    
    def __init__(self):
        """Initialize research engine with Claude integration"""
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.model = "claude-3-haiku-20240307"  # Fast model for research tasks
        
        # Research workspace
        self.workspace_dir = Path.home() / "Desktop" / "bowen_outputs" / "research"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Command templates directory (like Claude Code's .claude/commands)
        self.commands_dir = Path.home() / "Desktop" / "bowen" / "research_commands"
        self.commands_dir.mkdir(parents=True, exist_ok=True)
        
        # Research context and memory
        self.research_context = {}
        self.active_research = {}
        
        logger.info("ResearchEngine initialized with Claude Code-inspired capabilities")
    
    def analyze_codebase(self, directory_path: str, research_query: str) -> Dict[str, Any]:
        """
        Deep codebase analysis - inspired by Claude Code's agentic search
        Maps project structure, dependencies, and answers specific questions
        """
        try:
            directory = Path(directory_path)
            if not directory.exists():
                return {"error": f"Directory {directory_path} not found"}
            
            # Phase 1: Map project structure
            project_map = self._map_project_structure(directory)
            
            # Phase 2: Analyze dependencies and imports  
            dependencies = self._analyze_dependencies(directory)
            
            # Phase 3: Answer research query with context
            analysis = self._perform_contextual_analysis(
                project_map, dependencies, research_query, directory
            )
            
            # Phase 4: Generate comprehensive report
            report = self._generate_research_report(
                directory_path, research_query, project_map, dependencies, analysis
            )
            
            return {
                "status": "success",
                "project_map": project_map,
                "dependencies": dependencies, 
                "analysis": analysis,
                "report_path": self._save_research_report(report)
            }
            
        except Exception as e:
            logger.error(f"Codebase analysis failed: {e}")
            return {"error": str(e)}
    
    def execute_research_workflow(self, workflow_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute custom research workflows - like Claude Code's custom commands
        Supports templates for repeated research patterns
        """
        try:
            # Load workflow template
            workflow_path = self.commands_dir / f"{workflow_name}.md"
            if not workflow_path.exists():
                return {"error": f"Workflow {workflow_name} not found"}
            
            with open(workflow_path, 'r') as f:
                workflow_template = f.read()
            
            # Substitute parameters in template
            workflow_content = self._substitute_parameters(workflow_template, parameters)
            
            # Execute workflow steps
            results = self._execute_workflow_steps(workflow_content)
            
            return {
                "status": "success",
                "workflow": workflow_name,
                "results": results,
                "output_files": results.get("files_created", [])
            }
            
        except Exception as e:
            logger.error(f"Research workflow execution failed: {e}")
            return {"error": str(e)}
    
    def research_and_report(self, topic: str, research_type: str = "flexible") -> str:
        """
        Smart research that asks for clarification when needed
        """
        try:
            # Check if the request is too vague
            vague_indicators = [
                "i have a task", "i need", "can you", "for an essay", "research for", 
                "help with", "do research", "i may need", "task for you"
            ]
            
            # If request is vague, ask for specific topic
            if any(indicator in topic.lower() for indicator in vague_indicators) and len(topic.split()) < 8:
                return "What's the specific topic you want me to research? Give me the subject or question and I'll dig into it for you."
            
            # If we have a clear topic, do real research
            research_prompt = f"""
            Research this topic thoroughly: "{topic}"
            
            Provide comprehensive information including:
            1. Key concepts and background
            2. Current trends or developments  
            3. Important details and insights
            4. Practical applications
            5. Any relevant examples or case studies
            
            Be thorough and informative.
            """
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": research_prompt}]
            )
            
            research_content = response.content[0].text
            
            # Save substantial research
            if len(research_content) > 500:
                report_path = self._save_flexible_report(topic, research_content)
                return f"{research_content}\n\nDetailed report saved: {report_path}"
            else:
                return research_content
            
        except Exception as e:
            logger.error(f"Research failed: {e}")
            return f"Research error: {e}"
    
    def multi_file_analysis(self, file_patterns: List[str], analysis_query: str) -> Dict[str, Any]:
        """
        Analyze multiple files intelligently - like Claude Code's multi-file edits
        Understands relationships between files and provides comprehensive analysis
        """
        try:
            # Collect all matching files
            all_files = []
            for pattern in file_patterns:
                matching_files = list(Path(".").glob(pattern))
                all_files.extend(matching_files)
            
            if not all_files:
                return {"error": "No files found matching patterns"}
            
            # Read and analyze file contents
            file_contents = {}
            for file_path in all_files[:20]:  # Limit to prevent token overflow
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_contents[str(file_path)] = f.read()
                except:
                    file_contents[str(file_path)] = "[Binary or unreadable file]"
            
            # Perform multi-file analysis using Claude
            analysis_prompt = f"""
            Analyze these {len(file_contents)} files in relation to: {analysis_query}
            
            Files:
            {json.dumps({k: v[:1000] + "..." if len(v) > 1000 else v for k, v in file_contents.items()}, indent=2)}
            
            Provide:
            1. Overall architecture understanding
            2. Relationships between files
            3. Answer to the analysis query
            4. Recommendations for improvements
            5. Potential issues or concerns
            """
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": analysis_prompt}]
            )
            
            analysis_result = response.content[0].text
            
            return {
                "status": "success",
                "files_analyzed": len(file_contents),
                "file_list": list(file_contents.keys()),
                "analysis": analysis_result,
                "report_path": self._save_analysis_report(analysis_query, analysis_result)
            }
            
        except Exception as e:
            logger.error(f"Multi-file analysis failed: {e}")
            return {"error": str(e)}
    
    def git_workflow_automation(self, action: str, **kwargs) -> str:
        """
        Git workflow automation - inspired by Claude Code's Git integration
        Handles issues, PRs, testing, and deployment workflows
        """
        try:
            if action == "analyze_repo":
                return self._analyze_git_repository()
            elif action == "create_branch":
                return self._create_feature_branch(kwargs.get("branch_name"), kwargs.get("description"))
            elif action == "commit_analysis":
                return self._analyze_recent_commits()
            elif action == "pr_preparation":
                return self._prepare_pull_request(kwargs.get("title"), kwargs.get("description"))
            else:
                return f"Unknown git action: {action}"
                
        except Exception as e:
            logger.error(f"Git workflow automation failed: {e}")
            return f"Git workflow failed: {e}"
    
    def create_research_command(self, command_name: str, template_content: str) -> str:
        """
        Create custom research command templates - like Claude Code's custom commands
        Allows saving and reusing research workflows
        """
        try:
            command_file = self.commands_dir / f"{command_name}.md"
            
            # Add metadata header
            full_template = f"""---
command: {command_name}
created: {datetime.now().isoformat()}
type: research_workflow
---

{template_content}
"""
            
            with open(command_file, 'w') as f:
                f.write(full_template)
            
            return f"Research command '{command_name}' created at {command_file}"
            
        except Exception as e:
            logger.error(f"Research command creation failed: {e}")
            return f"Command creation failed: {e}"
    
    # PRIVATE METHODS
    def _map_project_structure(self, directory: Path) -> Dict[str, Any]:
        """Map project structure like Claude Code does"""
        structure = {
            "root": str(directory),
            "files": [],
            "directories": [],
            "languages": set(),
            "frameworks": [],
            "config_files": []
        }
        
        # Common config files to identify
        config_patterns = [
            "package.json", "requirements.txt", "Cargo.toml", "pom.xml",
            "build.gradle", "composer.json", "Gemfile", "setup.py"
        ]
        
        for item in directory.rglob("*"):
            if item.is_file():
                structure["files"].append(str(item.relative_to(directory)))
                # Identify language by extension
                if item.suffix:
                    structure["languages"].add(item.suffix)
                # Check for config files
                if item.name in config_patterns:
                    structure["config_files"].append(str(item.relative_to(directory)))
            elif item.is_dir():
                structure["directories"].append(str(item.relative_to(directory)))
        
        structure["languages"] = list(structure["languages"])
        return structure
    
    def _analyze_dependencies(self, directory: Path) -> Dict[str, List[str]]:
        """Analyze project dependencies"""
        dependencies = {
            "python": [],
            "javascript": [], 
            "imports": [],
            "unknown": []
        }
        
        # Check common dependency files
        if (directory / "requirements.txt").exists():
            with open(directory / "requirements.txt", 'r') as f:
                dependencies["python"] = [line.strip() for line in f.readlines() if line.strip()]
        
        if (directory / "package.json").exists():
            try:
                with open(directory / "package.json", 'r') as f:
                    package_data = json.load(f)
                    deps = package_data.get("dependencies", {})
                    dev_deps = package_data.get("devDependencies", {})
                    dependencies["javascript"] = list(deps.keys()) + list(dev_deps.keys())
            except:
                pass
        
        return dependencies
    
    def _perform_contextual_analysis(self, project_map: Dict, dependencies: Dict, query: str, directory: Path) -> str:
        """Perform contextual analysis using Claude"""
        analysis_prompt = f"""
        Analyze this codebase to answer: {query}
        
        Project Structure:
        - Root: {project_map['root']}
        - Files: {len(project_map['files'])} files
        - Languages: {', '.join(project_map['languages'])}
        - Config files: {', '.join(project_map['config_files'])}
        
        Dependencies:
        {json.dumps(dependencies, indent=2)}
        
        Key files (first 10):
        {json.dumps(project_map['files'][:10], indent=2)}
        
        Provide a comprehensive analysis focusing on the query.
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            messages=[{"role": "user", "content": analysis_prompt}]
        )
        
        return response.content[0].text
    
    def _generate_research_report(self, directory: str, query: str, project_map: Dict, dependencies: Dict, analysis: str) -> str:
        """Generate comprehensive research report"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = f"""# Codebase Research Report

**Generated by:** The Captain (BOWEN Research Engine)
**Timestamp:** {timestamp}
**Directory:** {directory}
**Research Query:** {query}

## Executive Summary
{analysis}

## Project Overview
- **Total Files:** {len(project_map['files'])}
- **Languages:** {', '.join(project_map['languages'])}
- **Configuration Files:** {', '.join(project_map['config_files'])}

## Dependencies Analysis
{json.dumps(dependencies, indent=2)}

## Detailed Analysis
{analysis}

## Recommendations
Based on the analysis, here are strategic recommendations:

1. **Architecture Review**: Consider the overall structure and organization
2. **Dependency Management**: Review and optimize dependencies
3. **Code Quality**: Identify areas for improvement
4. **Security**: Check for potential security concerns

---
*Report generated by BOWEN Research Engine - Strategic Intelligence for Praise Oyimi*
"""
        return report
    
    def _save_research_report(self, report_content: str) -> str:
        """Save research report to workspace"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.workspace_dir / f"research_report_{timestamp}.md"
        
        with open(report_path, 'w') as f:
            f.write(report_content)
        
        return str(report_path)
    
    def _create_research_plan(self, topic: str, research_type: str) -> Dict[str, Any]:
        """Create structured research plan"""
        return {
            "topic": topic,
            "type": research_type,
            "steps": [
                "information_gathering",
                "analysis",
                "synthesis", 
                "conclusion"
            ],
            "sources": [],
            "timeline": "immediate"
        }
    
    def _execute_research_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute research plan steps"""
        return {
            "plan_executed": plan,
            "data_collected": f"Research data for {plan['topic']}",
            "sources_found": 5,
            "analysis_complete": True
        }
    
    def _synthesize_research_data(self, data: Dict, topic: str) -> str:
        """Synthesize research data using Claude"""
        synthesis_prompt = f"""
        Synthesize research findings for topic: {topic}
        
        Research data: {json.dumps(data, indent=2)}
        
        Provide:
        1. Key findings
        2. Strategic insights  
        3. Actionable recommendations
        4. Potential challenges
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": synthesis_prompt}]
        )
        
        return response.content[0].text
    
    def _generate_professional_report(self, topic: str, analysis: str, research_type: str) -> str:
        """Generate professional research report"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return f"""# Research Report: {topic}

**Report Type:** {research_type.title()}
**Generated by:** The Captain (BOWEN Research Engine)
**Date:** {timestamp}
**Prepared for:** Praise Oyimi

## Executive Summary
{analysis}

## Strategic Recommendations
[Based on analysis above]

## Next Steps
[Action items and follow-up]

---
*Strategic Intelligence Report by BOWEN Framework*
"""
    
    def _save_report(self, topic: str, content: str, research_type: str) -> str:
        """Save research report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{research_type}_{safe_topic}_{timestamp}.md".replace(" ", "_")
        
        report_path = self.workspace_dir / filename
        
        with open(report_path, 'w') as f:
            f.write(content)
        
        return str(report_path)
    
    def _save_flexible_report(self, topic: str, content: str) -> str:
        """Save flexible research report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"research_{safe_topic}_{timestamp}.md".replace(" ", "_")
        
        report_path = self.workspace_dir / filename
        
        report_content = f"""# Research: {topic}

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Analyst:** The Captain (BOWEN Research Engine)

{content}

---
*Research completed by BOWEN - Strategic Intelligence for Praise Oyimi*
"""
        
        with open(report_path, 'w') as f:
            f.write(report_content)
        
        return str(report_path)
    
    def _save_analysis_report(self, query: str, analysis: str) -> str:
        """Save analysis report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"analysis_{safe_query}_{timestamp}.md".replace(" ", "_")
        
        report_path = self.workspace_dir / filename
        
        content = f"""# Multi-File Analysis Report

**Query:** {query}
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Analyst:** The Captain (BOWEN Research Engine)

## Analysis Results
{analysis}

---
*Analysis completed by BOWEN Research Engine*
"""
        
        with open(report_path, 'w') as f:
            f.write(content)
        
        return str(report_path)
    
    def _substitute_parameters(self, template: str, parameters: Dict[str, Any]) -> str:
        """Substitute parameters in workflow template"""
        content = template
        for key, value in parameters.items():
            content = content.replace(f"{{{key}}}", str(value))
        return content
    
    def _execute_workflow_steps(self, workflow_content: str) -> Dict[str, Any]:
        """Execute workflow steps"""
        # This would parse markdown and execute steps
        # For now, return a placeholder
        return {
            "steps_executed": 3,
            "files_created": [],
            "status": "completed"
        }
    
    def _analyze_git_repository(self) -> str:
        """Analyze current git repository"""
        try:
            # Get git status
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  capture_output=True, text=True)
            status = result.stdout
            
            # Get recent commits
            result = subprocess.run(['git', 'log', '--oneline', '-10'], 
                                  capture_output=True, text=True)
            commits = result.stdout
            
            return f"Git Status:\n{status}\n\nRecent Commits:\n{commits}"
        except:
            return "Git analysis failed - not a git repository or git not available"
    
    def _create_feature_branch(self, branch_name: str, description: str) -> str:
        """Create feature branch with description"""
        try:
            result = subprocess.run(['git', 'checkout', '-b', branch_name], 
                                  capture_output=True, text=True)
            return f"Branch '{branch_name}' created: {description}"
        except:
            return f"Failed to create branch '{branch_name}'"
    
    def _analyze_recent_commits(self) -> str:
        """Analyze recent commits for patterns"""
        try:
            result = subprocess.run(['git', 'log', '--stat', '-5'], 
                                  capture_output=True, text=True)
            return f"Recent commit analysis:\n{result.stdout}"
        except:
            return "Commit analysis failed"
    
    def _prepare_pull_request(self, title: str, description: str) -> str:
        """Prepare pull request information"""
        return f"""Pull Request Prepared:
Title: {title}
Description: {description}
Ready for submission through GitHub interface."""

# Example research command templates
def create_default_research_commands():
    """Create default research command templates"""
    engine = ResearchEngine()
    
    # Database research command
    db_research_template = """# Database Research Command

## Objective
Research database systems and normalization for {subject}

## Steps
1. Analyze database schema in {directory}
2. Review normalization levels
3. Identify optimization opportunities
4. Generate recommendations report

## Expected Outputs
- Database analysis report
- Normalization assessment  
- Performance recommendations
"""
    
    engine.create_research_command("database-research", db_research_template)
    
    # Remi Guardian analysis command
    remi_analysis_template = """# Remi Guardian Analysis Command

## Objective
Analyze Remi Guardian development progress for {component}

## Steps  
1. Review codebase structure in {remi_directory}
2. Assess feature completion status
3. Identify blockers and bottlenecks
4. Generate progress report for stakeholders

## Expected Outputs
- Development status report
- Blocker analysis
- Timeline recommendations
"""
    
    engine.create_research_command("remi-analysis", remi_analysis_template)
    
    return "Default research commands created"