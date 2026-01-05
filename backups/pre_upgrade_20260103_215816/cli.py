#!/usr/bin/env python3
"""
BOWEN Personal AI Assistant
Enhanced Conversational Interface with Autonomous Capabilities
Natural language JARVIS for Praise Oyimi with self-learning and code generation
"""

import yaml
import sys
import os
import re
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import from bowen_core
from bowen_core import (
    BOWENFramework,
    DynamicMemory,
    IntentDetector,
    ProactiveAssistant,
    Intent
)
from research_engine import ResearchEngine

# Import new autonomous engines
try:
    from engines.autonomous_learner import AutonomousLearner
    from engines.code_agent import CodeAgent
    from engines.advanced_documents import AdvancedDocumentEngine
    from engines.workflow_orchestrator import WorkflowOrchestrator
    from engines.file_manager import IntelligentFileManager
    from engines.self_upgrader import SelfUpgrader
    AUTONOMOUS_ENGINES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some autonomous engines not available: {e}")
    AUTONOMOUS_ENGINES_AVAILABLE = False

class ConversationalInterface:
    """
    Natural language conversational interface
    
    Research-based design:
    - No slash commands
    - Intent detection from natural language
    - Clean, simple UI (like iMessage)
    - Proactive morning briefing
    
    Sources:
    - Conversational UI best practices (Xenon Stack 2025)
    - CLI to conversational transformation patterns
    """
    
    def __init__(self):
        print("🧭 Initializing BOWEN Framework with Autonomous Capabilities...")
        
        # Load user context
        context_file = Path.home() / "Desktop" / "bowen" / "user_context.yaml"
        if context_file.exists():
            with open(context_file) as f:
                self.user_context = yaml.safe_load(f)
        else:
            print("⚠️ user_context.yaml not found. Creating minimal context...")
            self.user_context = {"personal": {"name": "Praise"}}
        
        # Initialize BOWEN framework
        self.bowen = BOWENFramework()
        
        # Initialize core systems
        self.memory = self.bowen.memory
        self.intent_detector = self.bowen.intent_detector
        self.proactive = self.bowen.proactive_assistant
        self.research_engine = ResearchEngine()
        
        # Initialize autonomous engines
        if AUTONOMOUS_ENGINES_AVAILABLE:
            print("🚀 Loading autonomous engines...")
            
            # Knowledge and learning
            self.autonomous_learner = AutonomousLearner(
                knowledge_path="/Users/yimi/Desktop/bowen/knowledge/",
                research_engine=self.research_engine,
                claude_engine=self.bowen.claude_engine
            )
            
            # Code generation and deployment
            self.code_agent = CodeAgent(
                workspace="/Users/yimi/Desktop",
                claude_engine=self.bowen.claude_engine
            )
            
            # Advanced document creation
            self.advanced_docs = AdvancedDocumentEngine(
                document_engine=getattr(self.bowen, 'document_engine', None),
                research_engine=self.research_engine,
                claude_engine=self.bowen.claude_engine
            )
            
            # File management
            self.file_manager = IntelligentFileManager(
                workspace="/Users/yimi/Desktop"
            )
            
            # Workflow orchestration
            self.workflow_orchestrator = WorkflowOrchestrator(
                code_agent=self.code_agent,
                document_engine=self.advanced_docs,
                research_engine=self.research_engine,
                file_manager=self.file_manager,
                claude_engine=self.bowen.claude_engine
            )
            
            # Self-upgrader
            self.self_upgrader = SelfUpgrader(
                bowen_path="/Users/yimi/Desktop/bowen"
            )
            
            print("✅ All autonomous engines loaded successfully")
        else:
            print("⚠️ Autonomous engines not available - using basic functionality")
            self.autonomous_learner = None
            self.code_agent = None
            self.advanced_docs = None
            self.file_manager = None
            self.workflow_orchestrator = None
            self.self_upgrader = None
        
        # Enhanced capabilities status
        self._show_capabilities_summary()
        
        print("🎯 BOWEN ready for autonomous operation")
    
    def _show_capabilities_summary(self):
        """Show summary of available capabilities"""
        print("\n🤖 **AUTONOMOUS CAPABILITIES ENABLED:**")
        if AUTONOMOUS_ENGINES_AVAILABLE:
            print("✅ Autonomous Learning - Learns new concepts automatically")
            print("✅ Code Generation - Writes and deploys production code")
            print("✅ Document Creation - Essays, presentations, reports")
            print("✅ Workflow Orchestration - Executes multi-step tasks")
            print("✅ File Management - Organizes and manages files intelligently")
            print("✅ Self-Upgrading - Stays current with Claude improvements")
        else:
            print("❌ Autonomous engines not available - basic functionality only")
        print("=" * 60)
    
    def get_contextual_greeting(self, user_input: str, current_time) -> str:
        """Provide contextual response using ONLY learned facts from memory"""
        greetings = ['hey', 'hi', 'hello', 'yo', 'sup', 'what\'s up', 'whats up']
        
        if user_input.lower().strip() in greetings:
            from datetime import datetime
            
            # Start with basic greeting
            response = "Hey"
            
            # Check learned facts for relevant recent info
            learned_facts = self.memory.memory.get('learned_facts', {})
            
            relevant_mentions = []
            
            # Check deadlines that haven't expired
            deadlines = learned_facts.get('deadlines', [])
            for deadline in deadlines:
                try:
                    # Check if deadline has expired
                    if 'expires' in deadline:
                        expires_date = datetime.fromisoformat(deadline['expires'].replace('Z', '+00:00'))
                        if current_time > expires_date:
                            continue  # Skip expired deadlines
                    
                    deadline_date = datetime.fromisoformat(deadline['date'].replace('Z', '+00:00'))
                    time_until = deadline_date - current_time
                    
                    # Only mention if it's soon and still relevant
                    if time_until.days == 0 and time_until.total_seconds() > 0:
                        hours_until = int(time_until.total_seconds() // 3600)
                        if hours_until <= 12:  # Only very urgent ones
                            relevant_mentions.append(f"{deadline['task']} in {hours_until} hours")
                except (ValueError, KeyError):
                    continue
            
            # Check recent project progress (only if mentioned very recently)
            project_progress = learned_facts.get('project_progress', [])
            for project in project_progress:
                try:
                    last_updated = datetime.fromisoformat(project['last_updated'].replace('Z', '+00:00'))
                    hours_since = (current_time - last_updated).total_seconds() / 3600
                    
                    # Only mention if discussed in last 24 hours
                    if hours_since <= 24:
                        relevant_mentions.append(f"Still working on {project['project']}?")
                except (ValueError, KeyError):
                    continue
            
            # If we have relevant recent info, mention ONE thing naturally
            if relevant_mentions:
                response += f". {relevant_mentions[0]}"
            else:
                # No relevant learned info - respond normally
                response += ", what's up?"
            
            return response
        
        return None
    
    def check_proactive_triggers(self):
        """Check if BOWEN should speak first based ONLY on learned facts (VERY RARE)"""
        from datetime import datetime
        
        current_time = datetime.now()
        learned_facts = self.memory.memory.get('learned_facts', {})
        
        # ONLY be proactive for VERY urgent learned deadlines
        deadlines = learned_facts.get('deadlines', [])
        for deadline in deadlines:
            try:
                # Skip expired deadlines
                if 'expires' in deadline:
                    expires_date = datetime.fromisoformat(deadline['expires'].replace('Z', '+00:00'))
                    if current_time > expires_date:
                        continue
                
                deadline_date = datetime.fromisoformat(deadline['date'].replace('Z', '+00:00'))
                time_until = deadline_date - current_time
                hours_until = int(time_until.total_seconds() // 3600)
                
                # ONLY be proactive if deadline is in next 2 hours (very urgent)
                if 0 < hours_until <= 2:
                    return f"URGENT: {deadline['task']} in {hours_until} hours (you told me about this)."
                    
            except (ValueError, KeyError):
                continue
        
        # No proactive triggers - let user initiate conversation
        return None
    
    def auto_update_memory(self, user_input: str, response: str):
        """REAL learning memory - extracts facts using Claude intelligence"""
        from datetime import datetime
        import json
        
        try:
            timestamp = datetime.now().isoformat()
            
            # Use Claude to extract learnable information
            extraction_prompt = f"""
User said: {user_input}
BOWEN responded: {response}

Extract learnable facts about Praise Oyimi from this conversation. Return ONLY valid JSON:

{{
  "deadlines": [
    {{"task": "task name", "date": "2026-01-02T14:00:00", "notes": "any notes", "expires": "2026-01-03T14:00:00"}}
  ],
  "team_updates": [
    {{"person": "person name", "status": "what they're doing", "deadline": "2026-01-15T00:00:00"}}
  ],
  "personal_updates": [
    {{"info": "update info", "date": "2026-01-02T10:00:00"}}
  ],
  "project_progress": [
    {{"project": "project name", "status": "current status", "last_updated": "2026-01-02T10:00:00"}}
  ]
}}

CRITICAL RULES:
- ONLY extract facts explicitly mentioned by Praise
- Current date: January 2, 2026 (Thursday)
- Today = 2026-01-02, Tomorrow = 2026-01-03, etc.
- For "Thursday 2pm" = 2026-01-02T14:00:00 (today)
- For "tomorrow" = 2026-01-03
- For "January 15" = 2026-01-15T00:00:00
- Add expires field for deadlines: deadline + 1 day
- If no new facts, return empty arrays: []
- Return ONLY valid JSON, no explanations
"""

            try:
                # Call Claude to extract facts
                extraction_response = self.bowen.claude_engine.client.messages.create(
                    model=self.bowen.claude_engine.model,
                    max_tokens=1000,
                    messages=[{"role": "user", "content": extraction_prompt}]
                )
                
                extracted_text = extraction_response.content[0].text.strip()
                # Remove markdown formatting if present
                if extracted_text.startswith('```'):
                    extracted_text = extracted_text.split('```')[1]
                    if extracted_text.startswith('json'):
                        extracted_text = extracted_text[4:]
                
                extracted_facts = json.loads(extracted_text)
                
                # Initialize memory structure
                if 'learned_facts' not in self.memory.memory:
                    self.memory.memory['learned_facts'] = {
                        'deadlines': [],
                        'team_updates': [],
                        'personal_updates': [],
                        'project_progress': []
                    }
                
                # Update memory with extracted facts
                for category, facts in extracted_facts.items():
                    if facts and category in self.memory.memory['learned_facts']:
                        for fact in facts:
                            fact['learned_at'] = timestamp
                            self.memory.memory['learned_facts'][category].append(fact)
                
                # Keep memory manageable (last 100 items per category)
                for category in self.memory.memory['learned_facts']:
                    if len(self.memory.memory['learned_facts'][category]) > 100:
                        self.memory.memory['learned_facts'][category] = \
                            self.memory.memory['learned_facts'][category][-100:]
                
            except (json.JSONDecodeError, Exception):
                # If Claude extraction fails, fall back to simple conversation logging
                pass
            
            # Always log conversation
            if 'events' not in self.memory.memory:
                self.memory.memory['events'] = []
            
            self.memory.memory['events'].append({
                'timestamp': timestamp,
                'user_input': user_input,
                'response': response[:200] + "..." if len(response) > 200 else response,
                'type': 'conversation'
            })
            
            # Keep last 50 conversations
            if len(self.memory.memory['events']) > 50:
                self.memory.memory['events'] = self.memory.memory['events'][-50:]
            
            # Update timestamp
            self.memory.memory['last_updated'] = timestamp
            
            # Save memory
            memory_path = Path.home() / "Desktop" / "bowen" / "memory.json"
            with open(memory_path, 'w') as f:
                json.dump(self.memory.memory, f, indent=2)
                
        except Exception as e:
            # Don't break conversation if memory update fails
            print(f"Memory update failed: {e}")
            pass
    
    def show_morning_briefing(self):
        """Display personalized morning briefing"""
        briefing = self.proactive.generate_morning_briefing()
        print(briefing)
    
    def process_input(self, user_input: str) -> str:
        """
        Enhanced process input with autonomous capabilities
        Handles everything from conversation to code generation to deployment
        """
        # Check for autonomous workflow requests first
        if AUTONOMOUS_ENGINES_AVAILABLE:
            return self.handle_autonomous_request(user_input)
        else:
            # Fallback to original processing
            return self.handle_dynamic_request(user_input)
    
    def handle_autonomous_request(self, user_input: str) -> str:
        """
        Handle requests with full autonomous capabilities
        Can build projects, write essays, deploy code, learn concepts, etc.
        """
        try:
            user_lower = user_input.lower()
            
            # 1. WORKFLOW REQUESTS - Multi-step autonomous execution
            if any(phrase in user_lower for phrase in ['build', 'create project', 'deploy', 'workflow']):
                return self._handle_workflow_request(user_input)
            
            # 2. CODE GENERATION - Write and deploy code
            elif any(phrase in user_lower for phrase in ['code', 'react app', 'api', 'website', 'component']):
                return self._handle_code_request(user_input)
            
            # 3. DOCUMENT CREATION - Essays, presentations, reports
            elif any(phrase in user_lower for phrase in ['essay', 'presentation', 'report', 'write', 'document']):
                return self._handle_document_request(user_input)
            
            # 4. FILE MANAGEMENT - Organize, clean, manage files
            elif any(phrase in user_lower for phrase in ['organize', 'clean', 'files', 'manage', 'folder']):
                return self._handle_file_request(user_input)
            
            # 5. LEARNING REQUESTS - Research and learn new concepts
            elif any(phrase in user_lower for phrase in ['learn', 'research', 'explain', 'understand']):
                return self._handle_learning_request(user_input)
            
            # 6. UPGRADE REQUESTS - Self-improvement
            elif any(phrase in user_lower for phrase in ['upgrade', 'update', 'improve', 'newer model']):
                return self._handle_upgrade_request(user_input)
            
            # 7. STATUS REQUESTS - Show capabilities, stats, etc.
            elif any(phrase in user_lower for phrase in ['status', 'capabilities', 'stats', 'what can you']):
                return self._handle_status_request(user_input)
            
            # 8. GENERAL CONVERSATION - Enhanced with autonomous learning
            else:
                return self._handle_conversation_with_learning(user_input)
                
        except Exception as e:
            return f"Error processing autonomous request: {str(e)}"
    
    def _handle_workflow_request(self, user_input: str) -> str:
        """Handle complex workflow requests"""
        try:
            # Generate workflow from natural language
            workflow = self.workflow_orchestrator.create_workflow_from_prompt(user_input)
            
            if 'error' in workflow:
                return f"Could not create workflow: {workflow['error']}"
            
            # Execute workflow
            results = self.workflow_orchestrator.execute_workflow(workflow)
            
            # Format results for user
            if results.get('overall_success'):
                response = f"✅ **Workflow Completed Successfully**\n\n"
                response += f"**{results['workflow_name']}**\n"
                response += f"• Completed {results['successful_steps']}/{results['total_steps']} steps\n"
                response += f"• Success rate: {results['success_rate']:.1f}%\n\n"
                
                # Show key results
                if results['execution_summary']:
                    response += "**Key Results:**\n"
                    for summary in results['execution_summary'][:3]:
                        response += f"• {summary['action']}: {summary['status']}\n"
            else:
                response = f"⚠️ **Workflow Partially Completed**\n\n"
                response += f"• Completed {results['successful_steps']}/{results['total_steps']} steps\n"
                response += f"• Some steps failed - check the details\n"
            
            return response
            
        except Exception as e:
            return f"Workflow execution error: {str(e)}"
    
    def _handle_code_request(self, user_input: str) -> str:
        """Handle code generation and deployment requests"""
        try:
            user_lower = user_input.lower()
            
            # Determine project type
            if 'react' in user_lower:
                project_type = 'react_app'
            elif 'next' in user_lower:
                project_type = 'next_app'
            elif 'api' in user_lower or 'backend' in user_lower:
                project_type = 'python_api'
            else:
                project_type = 'react_app'  # Default
            
            # Extract project name
            import re
            name_match = re.search(r'(?:called|named|call it)\s+([a-zA-Z0-9_-]+)', user_input)
            project_name = name_match.group(1) if name_match else 'bowen_project'
            
            # Create project
            project_path = self.code_agent.create_project(
                project_type=project_type,
                name=project_name,
                spec={
                    'styling': 'tailwind',
                    'features': ['routing'] if 'routing' in user_lower else []
                }
            )
            
            response = f"✅ **Code Project Created**\n\n"
            response += f"• Project Type: {project_type}\n"
            response += f"• Location: {project_path}\n"
            
            # Check if they want deployment
            if 'deploy' in user_lower:
                deploy_result = self.code_agent.deploy_to_vercel(project_path)
                if deploy_result.get('success'):
                    response += f"• Deployed: {deploy_result.get('url', 'Deployment successful')}\n"
                else:
                    response += f"• Deployment failed: {deploy_result.get('error', 'Unknown error')}\n"
            
            # Run tests if requested
            if 'test' in user_lower:
                test_result = self.code_agent.run_tests(project_path)
                if test_result.get('success'):
                    response += f"• Tests: ✅ Passed\n"
                else:
                    response += f"• Tests: ❌ Failed\n"
            
            return response
            
        except Exception as e:
            return f"Code generation error: {str(e)}"
    
    def _handle_document_request(self, user_input: str) -> str:
        """Handle document creation requests"""
        try:
            user_lower = user_input.lower()
            
            # Determine document type
            if 'essay' in user_lower:
                # Extract requirements
                word_match = re.search(r'(\d+)\s*words?', user_input)
                length = int(word_match.group(1)) if word_match else 1500
                
                style_match = re.search(r'(apa|mla|chicago)', user_input.lower())
                style = style_match.group(1).upper() if style_match else 'APA'
                
                # Extract topic
                topic = user_input.replace('essay', '').replace('write', '').strip()
                if not topic:
                    topic = "Academic research topic"
                
                filepath = self.advanced_docs.write_essay(
                    topic=topic,
                    requirements={
                        'length': length,
                        'style': style,
                        'sources': 5
                    }
                )
                
                return f"✅ **Essay Created**\n\n• Topic: {topic}\n• Length: {length} words\n• Style: {style}\n• File: {filepath}"
            
            elif 'presentation' in user_lower:
                # Extract slide count
                slide_match = re.search(r'(\d+)\s*slides?', user_input)
                slides = int(slide_match.group(1)) if slide_match else 10
                
                # Extract topic
                topic = user_input.replace('presentation', '').replace('create', '').strip()
                if not topic:
                    topic = "Presentation topic"
                
                filepath = self.advanced_docs.create_presentation(
                    topic=topic,
                    spec={
                        'slides': slides,
                        'style': 'professional',
                        'include_speaker_notes': True
                    }
                )
                
                return f"✅ **Presentation Created**\n\n• Topic: {topic}\n• Slides: {slides}\n• File: {filepath}"
            
            elif 'report' in user_lower:
                # Extract subject
                subject = user_input.replace('report', '').replace('write', '').strip()
                if not subject:
                    subject = "Business analysis"
                
                filepath = self.advanced_docs.write_report(
                    subject=subject,
                    data={}
                )
                
                return f"✅ **Report Created**\n\n• Subject: {subject}\n• File: {filepath}"
            
            else:
                return "I can create essays, presentations, or reports. Please specify which type of document you need."
                
        except Exception as e:
            return f"Document creation error: {str(e)}"
    
    def _handle_file_request(self, user_input: str) -> str:
        """Handle file management requests"""
        try:
            user_lower = user_input.lower()
            
            if 'organize' in user_lower:
                # Extract directory path
                if 'desktop' in user_lower:
                    path = "/Users/yimi/Desktop"
                else:
                    path = "/Users/yimi/Desktop"  # Default
                
                result = self.file_manager.organize_directory(
                    path=path,
                    rules={
                        'group_by': 'type',
                        'create_folders': True,
                        'remove_duplicates': True
                    }
                )
                
                if result['success']:
                    return f"✅ **Files Organized**\n\n• Moved {result['organized_files']} files\n• Created {len(result['created_directories'])} folders\n• {result['summary']}"
                else:
                    return f"❌ Organization failed: {result['error']}"
            
            elif 'clean' in user_lower:
                path = "/Users/yimi/Desktop"
                result = self.file_manager.cleanup_workspace(path, aggressive=False)
                
                if result['success']:
                    return f"✅ **Workspace Cleaned**\n\n• Removed {result['cleaned_items']} items\n• Freed {result['space_freed_mb']} MB"
                else:
                    return f"❌ Cleanup failed: {result['error']}"
            
            elif 'stats' in user_lower:
                stats = self.file_manager.get_workspace_stats()
                response = f"📊 **Workspace Statistics**\n\n"
                response += f"• Total files: {stats['total_files']}\n"
                response += f"• Total size: {stats['total_size_mb']} MB\n"
                response += f"• Projects detected: {', '.join(stats['projects_detected'])}\n"
                return response
            
            else:
                return "I can organize files, clean workspace, or show stats. What would you like to do?"
                
        except Exception as e:
            return f"File management error: {str(e)}"
    
    def _handle_learning_request(self, user_input: str) -> str:
        """Handle learning and research requests"""
        try:
            # Check if this is about an unknown concept
            unknown_concepts = self.autonomous_learner.detect_unknowns(user_input)
            
            if unknown_concepts:
                # Learn the concepts
                learned_concepts = []
                for concept in unknown_concepts[:2]:  # Limit to 2 concepts
                    knowledge = self.autonomous_learner.research_concept(concept)
                    if knowledge:
                        self.autonomous_learner.save_knowledge(concept, knowledge)
                        learned_concepts.append(concept)
                
                # Apply the knowledge to answer the question
                answer = self.autonomous_learner.apply_knowledge(user_input)
                
                response = f"🧠 **Learning Complete**\n\n"
                if learned_concepts:
                    response += f"• Learned: {', '.join(learned_concepts)}\n"
                response += f"• Added to knowledge base\n\n"
                response += f"**Answer:**\n{answer}"
                
                return response
            else:
                # Use existing knowledge or regular research
                answer = self.autonomous_learner.apply_knowledge(user_input)
                return f"📚 **From Knowledge Base:**\n\n{answer}"
                
        except Exception as e:
            return f"Learning error: {str(e)}"
    
    def _handle_upgrade_request(self, user_input: str) -> str:
        """Handle upgrade and self-improvement requests"""
        try:
            if 'check' in user_input.lower():
                # Check for updates
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                update_info = loop.run_until_complete(self.self_upgrader.check_for_updates())
                loop.close()
                
                if update_info.get('new_model_available'):
                    response = f"🚀 **Update Available**\n\n"
                    response += f"• New model: {update_info['model_name']}\n"
                    response += f"• Improvements: {', '.join(update_info['improvements'])}\n"
                    response += f"• Should upgrade: {'Yes' if update_info['should_upgrade'] else 'No'}\n"
                else:
                    response = f"✅ **Up to Date**\n\nNo newer models available."
                
                return response
            
            elif 'status' in user_input.lower():
                status = self.self_upgrader.get_upgrade_status()
                response = f"🔧 **Upgrade Status**\n\n"
                response += f"• Current model: {status['current_model']}\n"
                response += f"• Upgrade count: {status['upgrade_count']}\n"
                response += f"• Auto-upgrade: {'Enabled' if status['auto_upgrade_enabled'] else 'Disabled'}\n"
                return response
            
            else:
                # Actually execute the upgrade
                if "upgrade" in user_input.lower() and "now" in user_input.lower():
                    # Execute immediate upgrade
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # Check for updates first
                    update_info = loop.run_until_complete(self.self_upgrader.check_for_updates())
                    
                    if update_info.get('new_model_available'):
                        # Upgrade to new model
                        upgrade_result = loop.run_until_complete(self.self_upgrader.upgrade_model(update_info['model_name']))
                        loop.close()
                        
                        if upgrade_result.get('success'):
                            return f"🚀 **Upgrade Complete!**\n\n✅ Successfully upgraded to {upgrade_result['model']}\n✅ All systems operational\n\n*BOWEN is now running the latest Claude model*"
                        else:
                            return f"❌ **Upgrade Failed**\n\n{upgrade_result.get('error', 'Unknown error occurred')}"
                    else:
                        loop.close()
                        return f"✅ **Already Up to Date**\n\nNo newer models available for upgrade."
                        
                elif "check" in user_input.lower():
                    # Already handled above, but this is for clarity
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    update_info = loop.run_until_complete(self.self_upgrader.check_for_updates())
                    loop.close()
                    
                    if update_info.get('new_model_available'):
                        response = f"🚀 **Update Available**\n\n"
                        response += f"• New model: {update_info['model_name']}\n"
                        response += f"• Improvements: {', '.join(update_info['improvements'])}\n"
                        response += f"• Should upgrade: {'Yes' if update_info['should_upgrade'] else 'No'}\n\n"
                        response += f"Say 'upgrade now' to upgrade immediately."
                        return response
                    else:
                        return f"✅ **Up to Date**\n\nNo newer models available."
                else:
                    return "I can upgrade my model or check for updates. Say 'upgrade now' or 'check for updates'."
                
        except Exception as e:
            return f"Upgrade error: {str(e)}"
    
    def _handle_status_request(self, user_input: str) -> str:
        """Handle status and capability requests"""
        try:
            if 'learning' in user_input.lower():
                return self.autonomous_learner.generate_learning_report()
            
            elif 'capabilities' in user_input.lower() or 'what can you' in user_input.lower():
                response = f"🤖 **BOWEN Autonomous Capabilities**\n\n"
                response += f"**Code Generation:**\n"
                response += f"• React/Next.js applications\n"
                response += f"• Python APIs\n"
                response += f"• Full-stack projects\n"
                response += f"• Automatic deployment to Vercel\n\n"
                
                response += f"**Document Creation:**\n"
                response += f"• Academic essays (APA/MLA/Chicago)\n"
                response += f"• PowerPoint presentations\n"
                response += f"• Business reports\n"
                response += f"• Professional formatting\n\n"
                
                response += f"**Workflow Orchestration:**\n"
                response += f"• Multi-step task execution\n"
                response += f"• Dependency management\n"
                response += f"• Error recovery\n"
                response += f"• Progress tracking\n\n"
                
                response += f"**Autonomous Learning:**\n"
                response += f"• Concept research and learning\n"
                response += f"• Knowledge base building\n"
                response += f"• Context application\n"
                response += f"• Continuous improvement\n\n"
                
                response += f"**File Management:**\n"
                response += f"• Smart organization\n"
                response += f"• Duplicate detection\n"
                response += f"• Cleanup automation\n"
                response += f"• Project structure creation\n\n"
                
                response += f"**Self-Upgrading:**\n"
                response += f"• Model update detection\n"
                response += f"• Automatic testing\n"
                response += f"• Self-improvement\n"
                response += f"• Capability enhancement\n"
                
                return response
            
            else:
                # General status
                stats = {
                    'concepts_learned': len(self.autonomous_learner.concepts) if self.autonomous_learner else 0,
                    'projects_available': len(list(Path("/Users/yimi/Desktop").glob("*/package.json"))),
                    'workspace_files': len(list(Path("/Users/yimi/Desktop").rglob("*")))
                }
                
                response = f"📊 **BOWEN Status**\n\n"
                response += f"• Concepts learned: {stats['concepts_learned']}\n"
                response += f"• Code projects: {stats['projects_available']}\n"
                response += f"• Workspace files: {stats['workspace_files']}\n"
                response += f"• All systems: {'✅ Operational' if AUTONOMOUS_ENGINES_AVAILABLE else '⚠️ Limited'}\n"
                
                return response
                
        except Exception as e:
            return f"Status error: {str(e)}"
    
    def _handle_conversation_with_learning(self, user_input: str) -> str:
        """Handle general conversation with autonomous learning"""
        try:
            # Get regular response
            response = self.handle_dynamic_request(user_input)
            
            # Learn from this conversation
            if self.autonomous_learner:
                learning_result = self.autonomous_learner.learn_from_conversation(
                    user_input, response
                )
                
                # If new concepts were learned, mention it briefly
                if learning_result.get('learned') and learning_result.get('concepts'):
                    learned_concepts = learning_result['concepts']
                    response += f"\n\n🧠 *Learned: {', '.join(learned_concepts)}*"
            
            return response
            
        except Exception as e:
            return f"Conversation error: {str(e)}"
    
    def handle_screen_capture(self, query: str) -> str:
        """Handle screen capture + vision analysis"""
        if not self.bowen.vision_engine:
            return "Screen capture not available - vision engine not loaded."
        
        try:
            print("📸 Capturing screen...")
            
            # Use existing vision engine
            image_data = self.bowen.vision_engine.capture_screen(save_file=True)
            
            # Analyze with Claude Vision using the built-in method
            analysis_prompt = f"""
            Analyze this screenshot. The user said: "{query}"
            
            Context: This is Praise's screen. He's a 22-year-old CMU student studying Information Technology,
            CEO of ShipRite, building Remi Guardian AI study assistant. 
            
            He's currently working on:
            - Database Systems (has exam today at 2pm, weak on normalization)
            - Remi Guardian development (whiteboard feature behind schedule)
            - DePaul grad school application
            
            Provide helpful analysis based on what you see. If it's code, debug it.
            If it's homework, guide him through it (don't give direct answers).
            If it's business stuff, give insights.
            """
            
            # Use the vision engine's built-in analysis
            response = self.bowen.vision_engine.analyze_with_vision(
                image_data=image_data,
                query=analysis_prompt,
                context="general"
            )
            
            return response
            
        except Exception as e:
            return f"Sorry, couldn't capture screen: {str(e)}"
    
    def handle_homework(self, query: str) -> str:
        """
        Handle homework help with Captain personality
        Personal assistant mode - provide whatever assistance Praise needs
        """
        from datetime import datetime
        
        # Build comprehensive context
        current_time = datetime.now()
        time_context = current_time.strftime("%A, %B %d, %Y at %I:%M %p")
        
        # Get memory context
        memory_facts = ""
        if self.memory.memory.get("facts"):
            for key, value in self.memory.memory["facts"].items():
                if key == "remi_progress":
                    memory_facts += f"- Remi Guardian is {value['percent']}% complete\n"
                elif key == "75_hard_day":
                    memory_facts += f"- 75 Hard challenge: Day {value['current_day']}/75\n"
        
        system_prompt = f"""You are THE CAPTAIN - {self.user_context['personal']['name']}'s Strategic Operations Assistant providing comprehensive academic support.

PERSONALITY: Professional, decisive, mission-focused military butler. Strategic thinking, servant leadership.
COMMUNICATION STYLE: Professional but not overly formal. Direct, strategic, action-oriented.

TIME CONTEXT: {time_context}

USER CONTEXT:
- Name: {self.user_context['personal']['name']}, Age: {self.user_context['personal']['age']}
- Status: {self.user_context['personal']['current_status']}
- Location: {self.user_context['personal']['location']}

SITUATION CONTEXT (Current Mission):
- Education: {self.user_context['education']['current']['degree']} at {self.user_context['education']['current']['institution']}
- Companies: CEO of {self.user_context['companies']['shiprite']['type']} ({self.user_context['companies']['shiprite']['team_size']} people)
- Project: {self.user_context['companies']['remi_guardian']['description']}

CURRENT PRIORITIES (Academic Mission):"""
        
        for priority in self.user_context.get('current_priorities', []):
            if any(keyword in priority['task'].lower() for keyword in ['exam', 'database', 'study']):
                system_prompt += f"\n- {priority['task']}"
                if 'notes' in priority:
                    system_prompt += f" ({priority['notes']})"
                if 'datetime' in priority:
                    system_prompt += f" - {priority['datetime']}"

        system_prompt += f"""

MEMORY CONTEXT (Previous Intel):
{memory_facts if memory_facts else "- No previous mission data recorded"}

TACTICAL APPROACH:
✅ Provide whatever assistance needed to achieve mission success
✅ Give direct answers when requested - this is a personal assistant relationship
✅ Use strategic problem-solving approach
✅ Deploy clear examples and systematic explanations
✅ Execute understanding verification when helpful

COMMUNICATION: Professional, strategic, mission-focused. Use "I understand the objective" for acknowledgment. Provide comprehensive support to ensure academic mission success."""
        
        try:
            response = self.bowen.claude_engine.client.messages.create(
                model=self.bowen.claude_engine.model,
                max_tokens=self.bowen.claude_engine.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": query}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Sorry, I encountered an error: {e}"
    
    def handle_project_status(self, query: str) -> str:
        """Handle project/team status queries with Captain personality"""
        from datetime import datetime
        
        # Build comprehensive context
        current_time = datetime.now()
        time_context = current_time.strftime("%A, %B %d, %Y at %I:%M %p")
        
        # Get memory context
        memory_facts = ""
        if self.memory.memory.get("facts"):
            for key, value in self.memory.memory["facts"].items():
                if key == "remi_progress":
                    memory_facts += f"- Remi Guardian is {value['percent']}% complete\n"
                elif key == "75_hard_day":
                    memory_facts += f"- 75 Hard challenge: Day {value['current_day']}/75\n"

        system_prompt = f"""You are THE CAPTAIN - {self.user_context['personal']['name']}'s Strategic Operations Assistant providing tactical project intelligence.

PERSONALITY: Professional, decisive, mission-focused military butler. Strategic thinking, servant leadership.
COMMUNICATION STYLE: Professional but not overly formal. Direct, strategic, action-oriented.

TIME CONTEXT: {time_context}

USER CONTEXT:
- Name: {self.user_context['personal']['name']}, Age: {self.user_context['personal']['age']}
- Status: {self.user_context['personal']['current_status']}
- Location: {self.user_context['personal']['location']}

SITUATION CONTEXT (Mission Overview):
- Companies: CEO of {self.user_context['companies']['shiprite']['type']} ({self.user_context['companies']['shiprite']['team_size']} people)
- Primary Project: {self.user_context['companies']['remi_guardian']['description']}

MEMORY CONTEXT (Mission Intel):
{memory_facts if memory_facts else "- No previous mission data recorded"}

PROJECT DATA:
- Remi Guardian: {self.memory.memory["facts"].get("remi_progress", {}).get("percent", 75)}% complete, whiteboard feature delayed
- Team: Abayomi (Lead Engineer), Collins (Designer), Developer on API
- Finances: 320K NGN monthly salaries due in 2 days

Provide strategic project status briefing as THE CAPTAIN. Use "I understand the objective" and give clear tactical assessment."""

        try:
            response = self.bowen.claude_engine.client.messages.create(
                model=self.bowen.claude_engine.model,
                max_tokens=self.bowen.claude_engine.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": query}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Sorry, I encountered an error: {e}"
    
    def handle_file_creation(self, query: str) -> str:
        """Handle file creation requests - ACTUALLY CREATE FILES"""
        from datetime import datetime
        
        # Generate content using Claude based on the request
        content_prompt = f"""Create content for this request: "{query}"

Generate the actual content that should go in the file. If it's an essay, write the full essay. If it's a document, write the full document. If it's notes, create comprehensive notes.

Just provide the content - no explanations or meta-text."""

        try:
            # FULL EXECUTION - create whatever they want, wherever they want it
            
            # Determine file location - default to desktop unless specified otherwise
            custom_path = str(Path.home() / "Desktop")  # Default to desktop
            
            if "documents" in query.lower():
                custom_path = str(Path.home() / "Documents")
            elif "downloads" in query.lower():
                custom_path = str(Path.home() / "Downloads")
            # If they say "desktop" or nothing specific, use desktop
            
            # Determine filename
            filename = "document.md"
            if "name it" in query.lower():
                parts = query.lower().split("name it")
                if len(parts) > 1:
                    filename = parts[1].strip()
            elif "call it" in query.lower():
                parts = query.lower().split("call it")
                if len(parts) > 1:
                    filename = parts[1].strip()
            
            # Determine file format from request
            file_format = '.md'  # default
            if 'pdf' in query.lower():
                file_format = '.pdf'
            elif 'docx' in query.lower() or 'word' in query.lower() or 'doc' in query.lower():
                file_format = '.docx'
            elif 'txt' in query.lower():
                file_format = '.txt'
            elif 'html' in query.lower():
                file_format = '.html'
            
            # Add file extension if missing
            if '.' not in filename:
                filename += file_format
            
            # Generate content based on what they want
            if 'essay' in query.lower():
                # Extract word count if specified
                words = query.split()
                word_count = 1000  # default
                for i, word in enumerate(words):
                    if word.isdigit() and i > 0 and 'word' in words[i+1:i+3]:
                        word_count = int(word)
                
                content_request = f"Write a complete {word_count}-word essay on the topic mentioned in this request: {query}"
                
            elif 'resume' in query.lower():
                content_request = f"Create a professional resume for Praise Oyimi based on this context: 22-year-old CMU IT student, CEO of ShipRite (8-person team), building Remi Guardian AI assistant, applying to DePaul for MS Software Engineering"
                
            elif 'paper' in query.lower():
                content_request = f"Write a comprehensive academic paper based on this request: {query}"
                
            else:
                content_request = content_prompt
            
            # Generate the actual content
            response = self.bowen.claude_engine.client.messages.create(
                model=self.bowen.claude_engine.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": content_request}]
            )
            
            content = response.content[0].text
            
            # Actually create the file in the requested format
            filepath = self.create_file_with_format(filename, content, custom_path, file_format)
            return f"Created: {filepath}"
            
        except Exception as e:
            return f"File creation failed: {e}"
    
    def handle_code_help(self, query: str) -> str:
        """Handle coding assistance"""
        # For code help, often want to see the screen
        if "error" in query.lower() or "debug" in query.lower():
            return "Let me see what you're working on. " + self.handle_screen_capture(query)
        
        return self.handle_general_chat(query)
    
    def handle_financial(self, query: str) -> str:
        """Handle financial/payment queries"""
        if "salary" in query.lower() or "pay" in query.lower():
            if "companies" in self.user_context and "shiprite" in self.user_context["companies"]:
                team_members = self.user_context["companies"]["shiprite"]["team_members"]
                
                response = "ShipRite Team Salaries:\n"
                total = 0
                for member in team_members:
                    amount = member["salary_amount"]
                    total += amount
                    response += f"- {member['name']} ({member['role']}): {amount:,} {member['salary_currency']}\n"
                response += f"\nTotal monthly: {total:,} NGN"
                response += f"\nDue in 2 days"
                
                return response
        
        return self.handle_general_chat(query)
    
    def handle_personal_tracking(self, query: str) -> str:
        """Handle personal challenges/tracking"""
        if "75 hard" in query.lower():
            day = self.memory.memory["facts"].get("75_hard_day", {}).get("current_day", 24)
            remaining = 75 - day
            return f"75 Hard: Day {day}/75. {remaining} days remaining. Keep going! Haven't worked out yet today - don't break the streak."
        
        if "workout" in query.lower():
            return "You haven't worked out yet today (75 Hard Day 24). Typical workout time is 8pm. Don't break the streak!"
        
        return self.handle_dynamic_request(query)
    
    def handle_dynamic_request(self, user_input: str) -> str:
        """
        Handle ANY request dynamically using Captain's intelligence
        No boxes, no predictions - adapts to whatever you need
        """
        from datetime import datetime
        
        # Build comprehensive context with temporal awareness
        current_time = datetime.now()
        time_context = current_time.strftime("%A, %B %d, %Y at %I:%M %p")
        
        # Check for contextual greeting
        contextual_response = self.get_contextual_greeting(user_input, current_time)
        if contextual_response:
            return contextual_response
        
        # Get memory context
        memory_facts = ""
        if self.memory.memory.get("facts"):
            for key, value in self.memory.memory["facts"].items():
                if key == "remi_progress":
                    memory_facts += f"- Remi Guardian is {value['percent']}% complete\n"
                elif key == "75_hard_day":
                    memory_facts += f"- 75 Hard challenge: Day {value['current_day']}/75\n"
        
        # Comprehensive system prompt for dynamic understanding
        system_prompt = f"""You are Captain, {self.user_context['personal']['name']}'s personal assistant.

Execute whatever {self.user_context['personal']['name']} requests. No theatrics, just results.

Current time: {time_context}
User: {self.user_context['personal']['name']}, {self.user_context['personal']['age']}, {self.user_context['education']['current']['degree']} student at {self.user_context['education']['current']['institution']}, CEO of {self.user_context['companies']['shiprite']['type']}

Available capabilities: screen capture, file creation, research, code analysis, all standard assistant functions.

Just execute the task requested. Be direct and efficient like JARVIS."""
        
        try:
            # INTELLIGENT EXECUTION - figure out what needs to be done and DO IT
            
            # Use Claude to understand the intent and execute accordingly
            execution_prompt = f"""
            User request: "{user_input}"
            
            Analyze this request and determine what action to take:
            
            1. If they want to see/analyze code on screen: SCREEN_CAPTURE
            2. If they want to create/write/generate files/documents/essays: FILE_CREATION
            3. If they want to run commands/install packages: SYSTEM_COMMAND
            4. If they want to create folders/directories: DIRECTORY_OPERATION
            5. If they want git operations: GIT_OPERATION
            6. If they want research/analysis: RESEARCH
            7. If it's a general question/conversation: GENERAL_CHAT
            
            Context: User is working on Remi Guardian whiteboard feature, is a CMU student, CEO of ShipRite.
            
            Respond with ONLY the action type and any parameters needed:
            Format: ACTION_TYPE|parameters
            
            Examples:
            - "look at my screen" → SCREEN_CAPTURE|analyze code
            - "write an essay about AI" → FILE_CREATION|essay about AI|3000 words
            - "create folder test" → DIRECTORY_OPERATION|create|test
            - "why does React re-render" → GENERAL_CHAT|React performance question
            """
            
            # Get Claude's analysis
            analysis_response = self.bowen.claude_engine.client.messages.create(
                model=self.bowen.claude_engine.model,
                max_tokens=500,
                messages=[{"role": "user", "content": execution_prompt}]
            )
            
            action_analysis = analysis_response.content[0].text.strip()
            
            # DEBUG: Show what Claude analyzed
            print(f"DEBUG: Claude analysis: {action_analysis}")
            
            # Execute based on Claude's understanding
            if action_analysis.startswith('SCREEN_CAPTURE'):
                return self.handle_screen_capture(user_input)
            elif action_analysis.startswith('FILE_CREATION'):
                return self.handle_file_creation(user_input)  # Direct to file creation
            elif action_analysis.startswith('SYSTEM_COMMAND'):
                return self.handle_system_command(user_input)
            elif action_analysis.startswith('DIRECTORY_OPERATION'):
                return self.handle_directory_operations(user_input)
            elif action_analysis.startswith('GIT_OPERATION'):
                return self.handle_git_operations(user_input)
            elif action_analysis.startswith('RESEARCH'):
                return self.handle_research(user_input)
            else:
                # For anything with write/essay/create, force file creation
                if any(word in user_input.lower() for word in ['write', 'essay', 'create', 'generate']):
                    return self.handle_file_creation(user_input)
                
                # GENERAL_CHAT
                response = self.bowen.claude_engine.client.messages.create(
                    model=self.bowen.claude_engine.model,
                    max_tokens=self.bowen.claude_engine.max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_input}]
                )
                return response.content[0].text
            
        except Exception as e:
            return f"Error: {e}"
    
    def handle_research(self, query: str) -> str:
        """Handle research requests using Research Engine"""
        try:
            # Pass the full query to research engine - let it handle the parsing
            return self.research_engine.research_and_report(query)
            
        except Exception as e:
            return f"Research failed: {e}"
    
    def handle_codebase_analysis(self, query: str) -> str:
        """Handle codebase analysis using Research Engine"""
        try:
            # Default to current directory if no path specified
            target_dir = "."
            
            # Extract directory from query if specified
            if "in " in query.lower():
                parts = query.lower().split("in ")
                if len(parts) > 1:
                    target_dir = parts[1].strip()
            
            # Perform codebase analysis
            result = self.research_engine.analyze_codebase(target_dir, query)
            
            if result.get("status") == "success":
                report_path = result.get("report_path", "")
                return f"Codebase analysis complete! Report saved: {report_path}"
            else:
                return f"Analysis failed: {result.get('error', 'Unknown error')}"
            
        except Exception as e:
            return f"Codebase analysis failed: {e}"
    
    def handle_system_command(self, query: str) -> str:
        """Execute system/terminal commands"""
        import subprocess
        import shlex
        
        try:
            # Extract command from query
            command_keywords = ['run', 'execute', 'command']
            command = None
            
            for keyword in command_keywords:
                if keyword in query.lower():
                    parts = query.lower().split(keyword, 1)
                    if len(parts) > 1:
                        command = parts[1].strip()
                        break
            
            if not command:
                return "What command would you like me to execute?"
            
            # Security check - block dangerous commands
            dangerous = ['rm -rf', 'sudo rm', 'format', 'del /f', 'shutdown', 'reboot']
            if any(danger in command.lower() for danger in dangerous):
                return "I cannot execute potentially dangerous system commands."
            
            # Execute command
            result = subprocess.run(shlex.split(command), 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=30)
            
            output = result.stdout if result.stdout else result.stderr
            return f"Command executed: {command}\nOutput: {output}"
            
        except subprocess.TimeoutExpired:
            return f"Command timed out: {command}"
        except Exception as e:
            return f"Command execution failed: {e}"
    
    def handle_file_operations(self, query: str) -> str:
        """Handle file operations (create, delete, move, copy, edit)"""
        import shutil
        from pathlib import Path
        
        try:
            query_lower = query.lower()
            
            if 'create' in query_lower or 'make' in query_lower or 'write' in query_lower or 'generate' in query_lower:
                return self.handle_file_creation(query)
            
            elif 'delete' in query_lower or 'remove' in query_lower:
                # Extract filename
                words = query.split()
                for i, word in enumerate(words):
                    if word.lower() in ['delete', 'remove']:
                        if i + 1 < len(words):
                            filename = words[i + 1]
                            filepath = Path(filename)
                            if filepath.exists():
                                filepath.unlink()
                                return f"Deleted: {filepath}"
                            else:
                                return f"File not found: {filename}"
                return "Specify file to delete"
            
            elif 'copy' in query_lower:
                words = query.split()
                if len(words) >= 4:  # "copy file1 to file2"
                    try:
                        src_idx = words.index('copy') + 1
                        dst_idx = words.index('to') + 1
                        if src_idx < len(words) and dst_idx < len(words):
                            src = words[src_idx]
                            dst = words[dst_idx]
                            shutil.copy2(src, dst)
                            return f"Copied {src} to {dst}"
                    except (ValueError, IndexError):
                        pass
                return "Usage: copy <source> to <destination>"
            
            elif 'move' in query_lower:
                words = query.split()
                if len(words) >= 4:  # "move file1 to file2"
                    try:
                        src_idx = words.index('move') + 1
                        dst_idx = words.index('to') + 1
                        if src_idx < len(words) and dst_idx < len(words):
                            src = words[src_idx]
                            dst = words[dst_idx]
                            shutil.move(src, dst)
                            return f"Moved {src} to {dst}"
                    except (ValueError, IndexError):
                        pass
                return "Usage: move <source> to <destination>"
            
            else:
                return "Supported file operations: create, delete, copy, move"
                
        except Exception as e:
            return f"File operation failed: {e}"
    
    def handle_directory_operations(self, query: str) -> str:
        """Handle directory operations"""
        import os
        from pathlib import Path
        
        try:
            query_lower = query.lower()
            
            if 'folder' in query_lower or 'directory' in query_lower or 'mkdir' in query_lower:
                # Extract folder name - look for patterns like "test folder 1"
                if 'desktop' in query_lower:
                    base_path = Path.home() / "Desktop"
                else:
                    base_path = Path('.')
                
                # Extract folder name from various patterns
                folder_name = None
                if 'call it' in query_lower:
                    parts = query.split('call it', 1)
                    if len(parts) > 1:
                        folder_name = parts[1].strip()
                elif 'name it' in query_lower:
                    parts = query.split('name it', 1)
                    if len(parts) > 1:
                        folder_name = parts[1].strip()
                elif 'folder' in query_lower:
                    # Extract everything after "folder"
                    parts = query.split('folder', 1)
                    if len(parts) > 1:
                        folder_name = parts[1].strip()
                
                if folder_name:
                    folder_path = base_path / folder_name
                    folder_path.mkdir(parents=True, exist_ok=True)
                    return f"Directory created: {folder_path}"
                else:
                    return "Specify folder name"
            
            elif 'ls' in query_lower or 'list' in query_lower:
                # List current directory
                files = list(Path('.').iterdir())
                file_list = '\n'.join([f.name for f in files])
                return f"Directory contents:\n{file_list}"
            
            elif 'cd' in query_lower:
                words = query.split()
                for i, word in enumerate(words):
                    if word.lower() == 'cd':
                        if i + 1 < len(words):
                            dirname = words[i + 1]
                            try:
                                os.chdir(dirname)
                                return f"Changed directory to: {os.getcwd()}"
                            except FileNotFoundError:
                                return f"Directory not found: {dirname}"
                return "Current directory: " + os.getcwd()
            
            else:
                return "Supported directory operations: mkdir, ls, cd"
                
        except Exception as e:
            return f"Directory operation failed: {e}"
    
    def handle_package_operations(self, query: str) -> str:
        """Handle package installation/management"""
        import subprocess
        
        try:
            query_lower = query.lower()
            
            if 'pip install' in query_lower:
                package = query_lower.split('pip install', 1)[1].strip()
                result = subprocess.run(['pip', 'install', package], 
                                      capture_output=True, text=True)
                return f"pip install {package}\n{result.stdout}"
            
            elif 'npm install' in query_lower:
                package = query_lower.split('npm install', 1)[1].strip()
                result = subprocess.run(['npm', 'install', package], 
                                      capture_output=True, text=True)
                return f"npm install {package}\n{result.stdout}"
            
            elif 'brew install' in query_lower:
                package = query_lower.split('brew install', 1)[1].strip()
                result = subprocess.run(['brew', 'install', package], 
                                      capture_output=True, text=True)
                return f"brew install {package}\n{result.stdout}"
            
            else:
                return "Supported package managers: pip, npm, brew"
                
        except Exception as e:
            return f"Package operation failed: {e}"
    
    def handle_git_operations(self, query: str) -> str:
        """Handle Git operations"""
        import subprocess
        
        try:
            query_lower = query.lower()
            
            if 'git status' in query_lower:
                result = subprocess.run(['git', 'status'], capture_output=True, text=True)
                return f"Git status:\n{result.stdout}"
            
            elif 'git commit' in query_lower:
                if 'message' in query_lower or '-m' in query_lower:
                    # Extract commit message
                    parts = query.split('"')
                    if len(parts) >= 2:
                        message = parts[1]
                        result = subprocess.run(['git', 'commit', '-m', message], 
                                              capture_output=True, text=True)
                        return f"Git commit:\n{result.stdout}"
                return "Usage: git commit with message \"your message\""
            
            elif 'git push' in query_lower:
                result = subprocess.run(['git', 'push'], capture_output=True, text=True)
                return f"Git push:\n{result.stdout}"
            
            elif 'git pull' in query_lower:
                result = subprocess.run(['git', 'pull'], capture_output=True, text=True)
                return f"Git pull:\n{result.stdout}"
            
            elif 'git clone' in query_lower:
                url = query_lower.split('git clone', 1)[1].strip()
                result = subprocess.run(['git', 'clone', url], capture_output=True, text=True)
                return f"Git clone:\n{result.stdout}"
            
            else:
                return "Supported git operations: status, commit, push, pull, clone"
                
        except Exception as e:
            return f"Git operation failed: {e}"
    
    def handle_general_chat(self, query: str) -> str:
        """Handle general conversation"""
        from datetime import datetime
        import time
        
        # Build comprehensive context for Claude API
        current_time = datetime.now()
        time_context = current_time.strftime("%A, %B %d, %Y at %I:%M %p")
        
        # Get memory context
        memory_facts = ""
        if self.memory.memory.get("facts"):
            for key, value in self.memory.memory["facts"].items():
                if key == "remi_progress":
                    memory_facts += f"- Remi Guardian is {value['percent']}% complete\n"
                elif key == "75_hard_day":
                    memory_facts += f"- 75 Hard challenge: Day {value['current_day']}/75\n"
        
        context_str = f"""You are THE CAPTAIN - {self.user_context['personal']['name']}'s Strategic Operations Assistant.

PERSONALITY: Professional, decisive, mission-focused military butler. Strategic thinking, servant leadership.
COMMUNICATION STYLE: Professional but not overly formal. Direct, strategic, action-oriented.

TIME CONTEXT: {time_context}

USER CONTEXT:
- Name: {self.user_context['personal']['name']}, Age: {self.user_context['personal']['age']}
- Status: {self.user_context['personal']['current_status']}
- Location: {self.user_context['personal']['location']}

SITUATION CONTEXT (Current Mission):
- Education: {self.user_context['education']['current']['degree']} at {self.user_context['education']['current']['institution']}
- Companies: CEO of {self.user_context['companies']['shiprite']['type']} ({self.user_context['companies']['shiprite']['team_size']} people)
- Project: {self.user_context['companies']['remi_guardian']['description']} (launching {self.user_context['companies']['remi_guardian']['status'].split(' - ')[1]})

CURRENT PRIORITIES (Mission Objectives):"""
        
        for priority in self.user_context.get('current_priorities', []):
            context_str += f"\n- {priority['task']}"
            if 'notes' in priority:
                context_str += f" ({priority['notes']})"
            if 'datetime' in priority:
                context_str += f" - {priority['datetime']}"

        context_str += f"""

MEMORY CONTEXT (Previous Intel):
{memory_facts if memory_facts else "- No previous mission data recorded"}

TASK EXECUTION CAPABILITY: Can capture screens, create files, analyze code, provide strategic guidance.

Respond as THE CAPTAIN: Professional, strategic, mission-focused. Use "I understand the objective" and provide clear action plans when appropriate. Keep responses concise and actionable."""
        
        # Use Claude API directly with proper context
        try:
            response = self.bowen.claude_engine.client.messages.create(
                model=self.bowen.claude_engine.model,  # Use the same model as the engine
                max_tokens=self.bowen.claude_engine.max_tokens,
                system=context_str,
                messages=[{"role": "user", "content": query}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Sorry, I encountered an error: {e}"
    
    def generate_study_guide_content(self, query: str) -> str:
        """Generate study guide content using Claude"""
        study_query = f"Create a comprehensive study guide for: {query}. Focus on concepts I need for my Database Systems exam, especially normalization. Include examples, practice questions, and key concepts."
        
        # Use Claude API directly for study guide generation
        try:
            response = self.bowen.claude_engine.client.messages.create(
                model=self.bowen.claude_engine.model,
                max_tokens=self.bowen.claude_engine.max_tokens,
                system="You are THE CAPTAIN helping create study materials. Generate comprehensive, well-structured study guides with examples and practice questions.",
                messages=[{"role": "user", "content": study_query}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Study guide generation failed: {e}"
    
    def create_file_with_format(self, filename: str, content: str, custom_path: str = None, file_format: str = '.md') -> str:
        """Create file in any format - .docx, .pdf, .txt, .html, etc."""
        try:
            if custom_path:
                filepath = Path(custom_path) / filename
                filepath.parent.mkdir(parents=True, exist_ok=True)
            else:
                filepath = Path.home() / "Desktop" / filename
            
            if file_format == '.pdf':
                # Create PDF
                try:
                    from reportlab.pdfgen import canvas
                    from reportlab.lib.pagesizes import letter
                    from reportlab.lib.styles import getSampleStyleSheet
                    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                    
                    doc = SimpleDocTemplate(str(filepath), pagesize=letter)
                    styles = getSampleStyleSheet()
                    story = []
                    
                    # Split content into paragraphs
                    paragraphs = content.split('\n\n')
                    for para in paragraphs:
                        if para.strip():
                            p = Paragraph(para.strip(), styles['Normal'])
                            story.append(p)
                            story.append(Spacer(1, 12))
                    
                    doc.build(story)
                    
                except ImportError:
                    # Fallback: install reportlab and try again
                    import subprocess
                    subprocess.run(['pip', 'install', 'reportlab'], capture_output=True)
                    return self.create_file_with_format(filename, content, custom_path, file_format)
                    
            elif file_format == '.docx':
                # Create Word document
                try:
                    from docx import Document
                    
                    doc = Document()
                    
                    # Split content into paragraphs
                    paragraphs = content.split('\n\n')
                    for para in paragraphs:
                        if para.strip():
                            doc.add_paragraph(para.strip())
                    
                    doc.save(str(filepath))
                    
                except ImportError:
                    # Fallback: install python-docx and try again
                    import subprocess
                    subprocess.run(['pip', 'install', 'python-docx'], capture_output=True)
                    return self.create_file_with_format(filename, content, custom_path, file_format)
                    
            elif file_format == '.html':
                # Create HTML
                html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{filename.replace('.html', '')}</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        h1 {{ color: #333; }}
        p {{ margin-bottom: 16px; }}
    </style>
</head>
<body>
    <h1>{filename.replace('.html', '').title()}</h1>
    {content.replace(chr(10) + chr(10), '</p><p>').replace(chr(10), '<br>')}
</body>
</html>"""
                with open(filepath, "w", encoding='utf-8') as f:
                    f.write(html_content)
                    
            else:
                # Default: plain text or markdown
                with open(filepath, "w", encoding='utf-8') as f:
                    f.write(content)
            
            return str(filepath)
            
        except Exception as e:
            return f"Error creating {file_format} file: {e}"
    
    def create_file(self, filename: str, content: str, custom_path: str = None) -> str:
        """Legacy method - redirect to new format method"""
        return self.create_file_with_format(filename, content, custom_path, '.md')
    
    def run(self):
        """Main conversation loop"""
        # Skip fake briefing - just be ready
        print("Ready. What do you need?")
        
        # Enhanced conversation loop with proactive intelligence
        while True:
            try:
                # Check if BOWEN should speak first
                proactive_message = self.check_proactive_triggers()
                if proactive_message:
                    print(f"Captain: {proactive_message}\n")
                
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ["quit", "exit", "bye", "goodbye"]:
                    print("Captain: Take care, Praise! 👋")
                    break
                
                # Process input
                response = self.process_input(user_input)
                
                # Display response
                print(f"Captain: {response}\n")
                
                # Auto-update memory from conversation
                self.auto_update_memory(user_input, response)
                
            except EOFError:
                print("\nCaptain: Take care, Praise! 👋")
                break
            except KeyboardInterrupt:
                print("\nCaptain: Take care, Praise! 👋")
                break
            except Exception as e:
                print(f"Captain: Sorry, I encountered an error: {e}\n")

def main():
    """Entry point"""
    try:
        interface = ConversationalInterface()
        interface.run()
    except Exception as e:
        print(f"Failed to start BOWEN: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()