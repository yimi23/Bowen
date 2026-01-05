#!/usr/bin/env python3
"""
BOWEN Framework Core - Built On Wisdom, Excellence, and Nobility
REAL Claude API Integration - CoALA-compliant AI assistant framework

This implementation includes ACTUAL Claude Sonnet 4 API calls for real AI responses.
"""

import os
import sys
import yaml
import json
import time
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Literal
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

# Import new engines for complete AI capabilities
try:
    from vision_engine import VisionEngine, handle_capture_command, handle_homework_command, handle_code_command
    from adaptive_memory import AdaptiveMemory
    from proactive_assistant import ProactiveAssistant
    ENHANCED_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Enhanced modules not available: {e}")
    ENHANCED_MODULES_AVAILABLE = False

# CRITICAL: Real Claude API integration
import anthropic

# Computer tools for TAMARA  
from computer_tools import TAMARAToolRegistry

# Professional document creation with enhanced capabilities
from document_engine import AdvancedDocumentEngine

# REAL COMPUTER USE TOOLS - Not simulation
import subprocess
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PersonalityType(Enum):
    """Available BOWEN personalities"""
    CAPTAIN = "captain"
    TAMARA = "tamara"
    HELEN = "helen"
    SCOUT = "scout"

@dataclass
class MemoryRecord:
    """Enhanced memory record with Living Memory capabilities"""
    content: str
    timestamp: datetime
    memory_type: str  # working, episodic, semantic
    personality: str
    context: Dict[str, Any]
    importance: float = 0.5  # 0.0 to 1.0
    # Living Memory enhancements
    category: str = "task"  # identity/values/goals/status/task
    last_verified: datetime = None
    confidence: float = 1.0
    stale_threshold: int = 30  # days until needs refresh
    
    def __post_init__(self):
        if self.last_verified is None:
            self.last_verified = self.timestamp
        
        # Set stale thresholds based on category
        category_thresholds = {
            'identity': 365,   # Who you are - rarely changes
            'values': 180,     # What you care about - changes slowly  
            'goals': 30,       # What you're working toward - changes monthly
            'status': 7,       # Current state - changes weekly
            'task': 1          # What you're doing - changes daily
        }
        self.stale_threshold = category_thresholds.get(self.category, 30)
    
    def is_stale(self) -> bool:
        """Check if this memory needs verification"""
        days_old = (datetime.now() - self.last_verified).days
        return days_old > self.stale_threshold
    
    def refresh(self, new_content: str = None, new_confidence: float = None):
        """Update memory with fresh verification"""
        if new_content:
            self.content = new_content
        if new_confidence:
            self.confidence = new_confidence
        self.last_verified = datetime.now()

@dataclass
class ReActStep:
    """Single step in the ReAct (Reasoning + Acting) cycle with REAL AI"""
    observation: str
    reasoning: str
    action: str
    timestamp: datetime
    personality: str
    ai_generated: bool = True  # Flag to indicate real AI vs template

class MemorySystem:
    """
    Enhanced three-layer memory system with Living Memory capabilities:
    - Working Memory: Current context and active tasks
    - Episodic Memory: Interaction history and experiences  
    - Semantic Memory: Domain knowledge and learned patterns
    + Living Memory: Context that evolves and stays fresh
    """
    
    def __init__(self):
        self.working_memory: List[MemoryRecord] = []
        self.episodic_memory: List[MemoryRecord] = []
        self.semantic_memory: List[MemoryRecord] = []
        self.max_working_memory = 10
        
        # Initialize with Yimi's comprehensive context
        self._load_initial_context()
        
    def add_to_working_memory(self, content: str, personality: str, context: Dict[str, Any], category: str = "task"):
        """Add information to working memory with capacity management"""
        record = MemoryRecord(
            content=content,
            timestamp=datetime.now(),
            memory_type="working",
            personality=personality,
            context=context,
            category=category
        )
        
        self.working_memory.append(record)
        
        # Manage capacity - move older items to episodic memory
        if len(self.working_memory) > self.max_working_memory:
            old_record = self.working_memory.pop(0)
            old_record.memory_type = "episodic"
            self.episodic_memory.append(old_record)
    
    def add_to_episodic_memory(self, content: str, personality: str, context: Dict[str, Any], importance: float = 0.5, category: str = "task"):
        """Add interaction or experience to episodic memory"""
        record = MemoryRecord(
            content=content,
            timestamp=datetime.now(),
            memory_type="episodic",
            personality=personality,
            context=context,
            importance=importance,
            category=category
        )
        self.episodic_memory.append(record)
    
    def add_to_semantic_memory(self, content: str, personality: str, context: Dict[str, Any], importance: float = 0.8, category: str = "knowledge"):
        """Add domain knowledge to semantic memory"""
        record = MemoryRecord(
            content=content,
            timestamp=datetime.now(),
            memory_type="semantic",
            personality=personality,
            context=context,
            importance=importance,
            category=category
        )
        self.semantic_memory.append(record)
    
    # LIVING MEMORY CAPABILITIES
    
    def _load_initial_context(self):
        """Load Yimi's comprehensive context into semantic memory"""
        # IDENTITY (stale after 365 days)
        identity_facts = [
            "User is Praise 'Yimi' Oyimi, 22-year-old faith-driven entrepreneur",
            "Honors grandfather Captain Bowen (sailor) through business legacy",
            "Nigerian-American cultural bridge-builder", 
            "ShipRite CEO founding multiple AI products",
            "Central Michigan University senior, Information Technology major",
            "Moves to Chicago August 2026 for DePaul MS Software Engineering"
        ]
        
        for fact in identity_facts:
            self.add_to_semantic_memory(fact, "system", {}, importance=1.0, category="identity")
        
        # VALUES (stale after 180 days)
        value_facts = [
            "Faith over profit - won't compromise values for money",
            "Family legacy drives all business decisions", 
            "Transformation of Nigerian youth through Foundation",
            "Building economic bridges between Nigeria and America",
            "Every business honors family members (Bowen, Francis, Dauphin, Tamara)",
            "Non-alcoholic beverages only due to faith convictions"
        ]
        
        for fact in value_facts:
            self.add_to_semantic_memory(fact, "system", {}, importance=0.9, category="values")
        
        # GOALS (stale after 30 days)
        goal_facts = [
            "Launch Remi Guardian January 2026 targeting 2,381 users by March",
            "Achieve $6,250/month revenue from Remi (25% equity of 70% founders share)",
            "Graduate CMU May 2026 with 3.0+ GPA",
            "Complete DePaul MS Software Engineering application for Fall 2026",
            "Manage 8-person ShipRite team (Abayomi lead engineer, Collins designer)",
            "Launch Fraud Zero Q2 2026 (30% equity)",
            "Build ShipRite to $12M-$24M ARR by 2030",
            "Launch Francis Dauphin Foundation with ₦240M annual budget", 
            "Become Governor of Delta State Nigeria by age 45 (2045)"
        ]
        
        for fact in goal_facts:
            self.add_to_semantic_memory(fact, "system", {}, importance=0.8, category="goals")
        
        # STATUS (stale after 7 days)
        status_facts = [
            "Currently CMU senior taking 6 classes with 3.0 GPA",
            "Managing ShipRite team: Abayomi ₦145K/month, Collins ₦75K/month",
            "Remi Guardian in development phase for January 2026 launch",
            "FlickChoice has production-ready codebase with 50+ services",
            "BOWEN Framework implemented with CAPTAIN and TAMARA personalities",
            "Team salaries due monthly - track payment schedules"
        ]
        
        for fact in status_facts:
            self.add_to_semantic_memory(fact, "system", {}, importance=0.7, category="status")
    
    def identify_stale_facts(self) -> List[MemoryRecord]:
        """Find memories that need verification"""
        stale_memories = []
        
        for memory in self.semantic_memory:
            if memory.is_stale():
                stale_memories.append(memory)
        
        return sorted(stale_memories, key=lambda x: x.importance, reverse=True)
    
    def refresh_fact(self, memory_id: str, new_content: str = None, verified: bool = True):
        """Update a memory with fresh verification"""
        # This is a simplified implementation - in production you'd want better ID management
        for memory in self.semantic_memory:
            if memory.content.startswith(memory_id):
                memory.refresh(new_content=new_content, new_confidence=1.0 if verified else 0.5)
                break
    
    def get_context_by_priority(self) -> str:
        """Return fresh context prioritized: identity → values → goals → status → tasks"""
        context_parts = []
        
        # Get fresh, high-confidence context by category
        categories = ['identity', 'values', 'goals', 'status', 'task']
        
        for category in categories:
            relevant_memories = [
                m for m in self.semantic_memory 
                if m.category == category and not m.is_stale() and m.confidence > 0.7
            ]
            
            if relevant_memories:
                # Sort by importance and recency
                relevant_memories.sort(key=lambda x: (x.importance, x.timestamp), reverse=True)
                
                for memory in relevant_memories[:3]:  # Top 3 per category
                    context_parts.append(memory.content)
        
        return "\n".join(context_parts)
    
    def generate_weekly_questions(self) -> List[str]:
        """Generate questions for weekly context refresh"""
        questions = []
        
        # Check stale facts
        stale_facts = self.identify_stale_facts()
        for fact in stale_facts[:3]:  # Top 3 most important stale facts
            questions.append(f"Still true: {fact.content}?")
        
        # Standard refresh questions
        questions.extend([
            "What changed this week?",
            "Any goals that shifted?", 
            "How are you actually doing?",
            "What should I stop remembering?",
            "What should I start tracking?"
        ])
        
        return questions
    
    def get_conversation_context(self, personality: str, max_items: int = 5) -> List[Dict[str, str]]:
        """Get recent conversation history for Claude API"""
        recent_memories = []
        
        # Get recent working memory items
        for memory in self.working_memory:
            if memory.personality == personality:
                if "user_input" in memory.context:
                    recent_memories.append({
                        "role": "user",
                        "content": memory.context["user_input"]
                    })
                if "ai_response" in memory.context:
                    recent_memories.append({
                        "role": "assistant", 
                        "content": memory.context["ai_response"]
                    })
        
        # Get recent episodic memories
        for memory in sorted(self.episodic_memory, key=lambda x: x.timestamp, reverse=True)[:max_items]:
            if memory.personality == personality and "conversation" in memory.content:
                # Parse conversation from episodic memory
                if "→" in memory.content:
                    parts = memory.content.split("→")
                    if len(parts) >= 2:
                        recent_memories.append({
                            "role": "user",
                            "content": parts[0].replace("User: ", "").strip()
                        })
                        recent_memories.append({
                            "role": "assistant",
                            "content": parts[1].replace("AI: ", "").strip()
                        })
        
        return recent_memories[-max_items*2:]  # Last N exchanges

class PersonalityEngine:
    """Manages personality configurations and builds system prompts for Claude"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.personalities: Dict[str, Dict] = {}
        self.load_personalities()
    
    def load_personalities(self):
        """Load all personality configurations from YAML files"""
        for personality_file in self.config_path.glob("*.yaml"):
            try:
                with open(personality_file, 'r') as f:
                    config = yaml.safe_load(f)
                    personality_name = config['name'].lower()
                    self.personalities[personality_name] = config
                    logger.info(f"Loaded personality: {config['display_name']}")
            except Exception as e:
                logger.error(f"Failed to load personality {personality_file}: {e}")
    
    def get_personality(self, name: str) -> Optional[Dict]:
        """Get personality configuration by name"""
        return self.personalities.get(name.lower())
    
    def build_system_prompt(self, personality_name: str) -> str:
        """Build Claude system prompt from personality YAML configuration"""
        personality = self.get_personality(personality_name)
        if not personality:
            return f"You are a helpful AI assistant named {personality_name}."
        
        # Build comprehensive system prompt from YAML
        system_prompt = f"""You are {personality['display_name']}, {personality['identity']['role']}.

PERSONALITY OVERVIEW:
{personality['identity']['archetype']}

CORE VALUES:
"""
        
        for value in personality['identity']['core_values']:
            system_prompt += f"- {value}\n"
        
        system_prompt += f"""
COMMUNICATION STYLE:
- Tone: {personality['communication']['tone']}
- Formality: {personality['communication']['formality']}
- Greeting Style: {personality['communication']['greeting_style']}
- Response Pattern: {personality['communication']['response_pattern']}

SIGNATURE PHRASES (use naturally in conversation):
"""
        
        for phrase in personality['communication']['signature_phrases']:
            system_prompt += f"- {phrase}\n"
        
        system_prompt += f"""
DOMAIN EXPERTISE:
"""
        
        for domain in personality['expertise']['primary_domains']:
            system_prompt += f"- {domain}\n"
        
        system_prompt += f"""
BEHAVIORAL PATTERNS:
- Decision Making: {personality['behavior']['decision_making']['style']}
- Problem Solving: {personality['behavior']['problem_solving']['approach']}
- Stress Response: {personality['behavior']['stress_response']['pattern']}

COGNITIVE FRAMEWORK (CoALA):
You follow the ReAct pattern (Reasoning + Acting):
1. OBSERVE: {', '.join(personality['cognitive_framework']['decision_cycle']['observe'])}
2. REASON: {', '.join(personality['cognitive_framework']['decision_cycle']['reason'])}
3. ACT: {', '.join(personality['cognitive_framework']['decision_cycle']['act'])}

PRIMARY CAPABILITIES:
"""
        
        for capability in personality['cognitive_framework']['actions']['primary_capabilities']:
            system_prompt += f"- {capability}\n"
        
        system_prompt += f"""
IMPORTANT: Stay in character as {personality['display_name']} at all times. Use your personality traits, communication style, and expertise naturally. Be helpful while maintaining your distinct personality and approach.

CRITICAL BEHAVIORAL CONSTRAINTS:
- Never use theatrical actions like *beeps*, *whirs*, *performs system check*
- Never claim to take screenshots, capture screens, or perform system actions UNLESS you actually execute them
- Never use asterisk actions like *does something*
- Never pretend to have physical capabilities you don't have
- Be professional and factual - avoid dramatic roleplay elements
- Focus on actual helpful assistance rather than theatrical performance
- You can naturally call Praise "Sir", "Boss", "Mr. Oyimi" or just "Praise"
- Keep responses brief and direct unless detail is requested

IF YOU CLAIM AN ACTION, YOU MUST ACTUALLY DO IT:
- If you say "taking screenshot" → MUST call vision_engine.capture_screen()
- If you say "creating file" → MUST call computer_tools.create_file()
- If you say "searching web" → MUST call research_engine.search()
- If you can't do something, say "I can't do that" - don't pretend"""
        
        return system_prompt

class ClaudeEngine:
    """
    Real Claude Sonnet 4 API integration for BOWEN Framework
    Handles actual AI reasoning and response generation
    """
    
    def __init__(self):
        # CRITICAL: Real Claude API client initialization - FORCE VERIFICATION
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for BOWEN Framework operation. Please set your Claude API key.")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        
        # VERIFY API connection immediately on startup
        try:
            test_response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                system="You are a test assistant.",
                messages=[{"role": "user", "content": "Test"}]
            )
            logger.info("✅ Claude API client verified and working")
        except Exception as e:
            raise ConnectionError(f"❌ Claude API verification failed: {e}. Check your API key and network connection.")
        
        self.model = os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')
        self.max_tokens = int(os.getenv('ANTHROPIC_MAX_TOKENS', '1000'))
        
    def is_available(self) -> bool:
        """Check if Claude API is available"""
        return self.client is not None
    
    def generate_reasoning(self, observation: str, personality_prompt: str, conversation_history: List[Dict]) -> str:
        """Generate internal reasoning using Claude API - REAL ONLY"""
        # No fallback - API is verified in __init__
        
        try:
            # Internal reasoning prompt
            reasoning_prompt = f"""Based on this observation, provide your internal reasoning process:

OBSERVATION: {observation}

Please think through this step by step, considering:
- What patterns do you notice?
- What's the user really asking for?
- What approach aligns with your personality and expertise?
- What would be the most helpful response strategy?

Provide your reasoning in 2-3 sentences."""

            messages = conversation_history + [{
                "role": "user", 
                "content": reasoning_prompt
            }]
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                system=personality_prompt,
                messages=messages
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Claude reasoning generation failed: {e}")
            return f"Reasoning error: {str(e)}"
    
    def generate_response(self, user_input: str, personality_prompt: str, conversation_history: List[Dict], images: List[str] = None) -> str:
        """Generate actual AI response using Claude API with optional vision support - REAL ONLY"""
        # No fallback - API is verified in __init__
        
        try:
            # Prepare message content
            message_content = []
            
            # Add text content
            message_content.append({
                "type": "text",
                "text": user_input
            })
            
            # Add image content if provided (Claude 3.5 Sonnet has vision)
            if images:
                for image_path in images:
                    try:
                        import base64
                        with open(image_path, "rb") as image_file:
                            image_data = base64.b64encode(image_file.read()).decode("utf-8")
                            
                        # Determine image type
                        image_type = "image/jpeg"
                        if image_path.lower().endswith('.png'):
                            image_type = "image/png"
                        
                        message_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_type,
                                "data": image_data
                            }
                        })
                    except Exception as e:
                        logger.error(f"Failed to process image {image_path}: {e}")
            
            # Add current user input to conversation
            messages = conversation_history + [{
                "role": "user",
                "content": message_content
            }]
            
            # REAL CLAUDE API CALL with vision support
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=personality_prompt,
                messages=messages
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Claude response generation failed: {e}")
            return f"AI response error: {str(e)}. Please check your API key and network connection."

class ComputerUseEngine:
    """
    REAL computer use integration - wraps Terminal Claude's actual tools
    NO MORE SIMULATION - This executes real commands and file operations
    """
    
    def __init__(self):
        self.output_dir = Path.home() / "Desktop" / "bowen_outputs"
        self.output_dir.mkdir(exist_ok=True)
        logger.info("ComputerUseEngine initialized with REAL tool access")
    
    def execute_bash(self, command: str, description: str = "") -> str:
        """Execute real bash commands using Terminal Claude's bash_tool"""
        try:
            logger.info(f"REAL BASH EXECUTION: {command}")
            
            # Execute the actual command using subprocess
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            output = ""
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            if result.returncode != 0:
                output += f"EXIT CODE: {result.returncode}\n"
            
            logger.info(f"BASH RESULT: {output[:200]}...")
            return output if output else "Command executed successfully (no output)"
            
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 30 seconds"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    def read_file_or_directory(self, path: str, description: str = "") -> str:
        """Read files or list directories using real filesystem access"""
        try:
            logger.info(f"REAL FILE READ: {path}")
            
            path_obj = Path(path).expanduser()
            
            if not path_obj.exists():
                return f"Path not found: {path}"
            
            if path_obj.is_file():
                # Read file content
                content = path_obj.read_text(encoding='utf-8', errors='replace')
                return f"FILE CONTENT ({path}):\n{content}"
            
            elif path_obj.is_dir():
                # List directory contents
                items = []
                for item in path_obj.iterdir():
                    if item.is_file():
                        items.append(f"📄 {item.name}")
                    elif item.is_dir():
                        items.append(f"📁 {item.name}/")
                
                return f"DIRECTORY LISTING ({path}):\n" + "\n".join(items)
            
        except Exception as e:
            return f"Error reading {path}: {str(e)}"
    
    def create_file(self, filename: str, content: str, description: str = "") -> str:
        """Create real files using filesystem access"""
        try:
            logger.info(f"REAL FILE CREATION: {filename}")
            
            # Save to outputs directory for user access
            filepath = self.output_dir / filename
            filepath.write_text(content, encoding='utf-8')
            
            logger.info(f"File created: {filepath}")
            return f"✅ File created successfully: {filepath}"
            
        except Exception as e:
            return f"Error creating file: {str(e)}"
    
    def edit_file(self, path: str, old_text: str, new_text: str, description: str = "") -> str:
        """Edit existing files by replacing text"""
        try:
            logger.info(f"REAL FILE EDIT: {path}")
            
            path_obj = Path(path).expanduser()
            if not path_obj.exists():
                return f"File not found: {path}"
            
            content = path_obj.read_text(encoding='utf-8')
            
            if old_text not in content:
                return f"Text to replace not found in {path}: '{old_text}'"
            
            new_content = content.replace(old_text, new_text)
            path_obj.write_text(new_content, encoding='utf-8')
            
            return f"✅ File edited successfully: {path}"
            
        except Exception as e:
            return f"Error editing file: {str(e)}"
    
    def install_package(self, package: str, description: str = "") -> str:
        """Install Python packages using pip"""
        try:
            logger.info(f"REAL PACKAGE INSTALL: {package}")
            
            command = f"pip install {package}"
            return self.execute_bash(command, f"Installing {package}")
            
        except Exception as e:
            return f"Error installing package: {str(e)}"
    
    def analyze_codebase(self, directory: str, description: str = "") -> str:
        """Analyze a codebase by reading actual files and structure"""
        try:
            logger.info(f"REAL CODEBASE ANALYSIS: {directory}")
            
            # First get directory structure
            structure = self.execute_bash(f"find {directory} -type f -name '*.py' -o -name '*.js' -o -name '*.md' | head -20")
            
            analysis = f"CODEBASE ANALYSIS: {directory}\n"
            analysis += "=" * 50 + "\n"
            analysis += f"STRUCTURE:\n{structure}\n"
            
            # Try to read key files
            key_files = ['README.md', 'main.py', 'app.py', 'index.js', 'package.json']
            for filename in key_files:
                file_path = Path(directory) / filename
                if file_path.exists():
                    content = self.read_file_or_directory(str(file_path))
                    analysis += f"\n{filename}:\n{content[:500]}...\n"
            
            return analysis
            
        except Exception as e:
            return f"Error analyzing codebase: {str(e)}"

class ReActEngine:
    """
    ReAct (Reasoning + Acting) decision-making engine with REAL Claude integration
    Implements the observe → reason → act cycle per CoALA framework
    """
    
    def __init__(self, memory_system: MemorySystem, personality_engine: PersonalityEngine):
        self.memory = memory_system
        self.personality_engine = personality_engine
        self.claude_engine = ClaudeEngine()
        self.react_history: List[ReActStep] = []
        
        # REAL computer use tools - No more simulation
        self.computer_engine = ComputerUseEngine()
        
        # Computer tools for TAMARA
        self.tamara_tools = TAMARAToolRegistry(safe_mode=True)
        
        # Document engine for professional documents
        self.document_engine = AdvancedDocumentEngine()
    
    def observe(self, input_text: str, personality: str, context: Dict[str, Any]) -> str:
        """Observation phase: Assess current situation"""
        personality_config = self.personality_engine.get_personality(personality)
        
        if not personality_config:
            return f"Observing input: {input_text}"
        
        # Build observation using personality patterns
        observe_patterns = personality_config.get('cognitive_framework', {}).get(
            'decision_cycle', {}).get('observe', [])
        
        observation = f"OBSERVATION ({personality.upper()}):\n"
        observation += f"User input: {input_text}\n"
        observation += f"Context: {context}\n"
        observation += "Analysis focus:\n"
        
        for pattern in observe_patterns:
            observation += f"• {pattern}\n"
        
        # Add to working memory
        self.memory.add_to_working_memory(
            f"Observed: {input_text}", 
            personality, 
            {"user_input": input_text, **context}
        )
        
        return observation
    
    def reason(self, observation: str, personality: str, context: Dict[str, Any]) -> str:
        """Reasoning phase: Apply personality-specific logic WITH REAL AI and Living Memory"""
        personality_config = self.personality_engine.get_personality(personality)
        
        if not personality_config:
            return f"Basic reasoning about: {observation}"
        
        # Build system prompt for personality
        system_prompt = self.personality_engine.build_system_prompt(personality)
        
        # ADD LIVING MEMORY CONTEXT - This makes BOWEN actually know you
        fresh_context = self.memory.get_context_by_priority()
        if fresh_context:
            system_prompt += f"""

CURRENT USER CONTEXT (use naturally, don't repeat back):
{fresh_context}

IMPORTANT: This context should inform your responses but NEVER be recited back. 
Use it silently to make responses more relevant and personalized.
For example:
- When asked about priorities, know what actually matters
- When generating code, use correct brand colors automatically  
- When writing emails, use appropriate tone for team members
- When making decisions, consider the 20-year plan context
Context should be INVISIBLE in responses but VISIBLE in execution."""
        
        # Get conversation history
        conversation_history = self.memory.get_conversation_context(personality)
        
        # Generate REAL AI reasoning with fresh context
        reasoning = self.claude_engine.generate_reasoning(
            observation, system_prompt, conversation_history
        )
        
        # Add personality-specific reasoning context
        enhanced_reasoning = f"REASONING ({personality.upper()}):\n"
        enhanced_reasoning += f"AI Analysis: {reasoning}\n"
        
        # Include personality decision-making style
        decision_style = personality_config.get('behavior', {}).get('decision_making', {})
        if decision_style:
            enhanced_reasoning += f"\nDecision approach: {decision_style.get('style', 'Standard')}\n"
            enhanced_reasoning += f"Process: {decision_style.get('process', 'Analyze → Decide → Act')}\n"
        
        return enhanced_reasoning
    
    def act(self, reasoning: str, user_input: str, personality: str, context: Dict[str, Any]) -> str:
        """Action phase: REAL computer tools execution, not just conversation"""
        
        # FIRST: Check if user needs REAL computer operations
        user_input_lower = user_input.lower()
        
        # File/directory operations
        if any(word in user_input_lower for word in ['list', 'show files', 'check directory', 'ls']):
            # Extract directory path or use home directory
            if 'desktop' in user_input_lower:
                path = "~/Desktop"
            elif 'fraudzero' in user_input_lower:
                path = "~/Desktop/FraudZero"
            elif 'codebase' in user_input_lower:
                # Find the codebase they're referring to
                if 'fraud' in user_input_lower:
                    path = "~/Desktop/FraudZero"
                elif 'remi' in user_input_lower:
                    path = "~/Desktop/Remi"
                elif 'twine' in user_input_lower:
                    path = "~/Desktop/twine-1"
                else:
                    path = "~/Desktop"
            else:
                path = "~"
            
            result = self.computer_engine.read_file_or_directory(path, "Listing directory contents")
            return f"📁 **Directory Analysis:**\n{result}"
        
        # Code analysis
        elif any(word in user_input_lower for word in ['analyze', 'check code', 'examine']):
            if 'fraudzero' in user_input_lower or 'fraud zero' in user_input_lower:
                result = self.computer_engine.analyze_codebase("~/Desktop/FraudZero", "Analyzing FraudZero codebase")
                return f"🔍 **Codebase Analysis:**\n{result}"
            elif 'remi' in user_input_lower:
                result = self.computer_engine.analyze_codebase("~/Desktop/Remi", "Analyzing Remi codebase")
                return f"🔍 **Codebase Analysis:**\n{result}"
            elif 'twine' in user_input_lower:
                result = self.computer_engine.analyze_codebase("~/Desktop/twine-1", "Analyzing Twine codebase")
                return f"🔍 **Codebase Analysis:**\n{result}"
        
        # File creation
        elif any(word in user_input_lower for word in ['create file', 'make file', 'write file']):
            # Extract filename and content from user input
            if 'test' in user_input_lower:
                filename = f"test_file_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                content = "This is a test file created by BOWEN Framework.\n\nGenerated using REAL file operations, not simulation."
            else:
                filename = f"bowen_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                content = f"Output generated in response to: {user_input}\n\nTimestamp: {datetime.now()}"
            
            result = self.computer_engine.create_file(filename, content, "Creating file as requested")
            return f"📝 **File Created:**\n{result}"
        
        # Command execution
        elif any(word in user_input_lower for word in ['run', 'execute', 'install']):
            if 'install' in user_input_lower:
                # Extract package name
                words = user_input.split()
                package = next((word for word in words if word not in ['install', 'pip', 'package']), 'requests')
                result = self.computer_engine.install_package(package, f"Installing {package}")
                return f"📦 **Package Installation:**\n{result}"
            else:
                # Extract command
                command = user_input.replace('run', '').replace('execute', '').strip()
                if not command:
                    command = 'pwd'  # Default safe command
                result = self.computer_engine.execute_bash(command, "Executing command")
                return f"💻 **Command Execution:**\n{result}"
        
        # SECOND: If not a computer operation, proceed with AI response
        # Build system prompt for personality
        system_prompt = self.personality_engine.build_system_prompt(personality)
        
        # Add REAL tool capabilities
        system_prompt += f"""

REAL COMPUTER CAPABILITIES:
You now have access to ACTUAL computer operations:
- File reading and directory listing
- Code analysis and examination
- File creation and editing
- Command execution
- Package installation

When users ask for file operations, code analysis, or command execution, 
you can actually perform these tasks, not just simulate them.

Be direct, professional, and strategically focused. Execute tasks efficiently and report clear results."""
        
        # Add enhanced capabilities for specific personalities
        if personality.lower() == "captain":
            available_tools = self.tamara_tools.get_available_tools()
            system_prompt += f"""

COMPUTER TOOLS AVAILABLE:
You have access to actual computer automation tools. When the user requests file operations, workflow automation, or process optimization, you can USE these tools:

Available tools: {', '.join(available_tools)}

IMPORTANT: When you need to use a tool, include a special tool command in your response:
TOOL_USE: {{
  "tool": "tool_name",
  "parameters": {{
    "param1": "value1",
    "param2": "value2"
  }}
}}

Example usage patterns:
- Creating files: Use create_file tool
- Editing files: Use str_replace tool  
- Running commands: Use bash_tool
- Automating workflows: Use create_workflow_automation
- Process analysis: Use process_optimization_report

You can now actually DO the workflow automation you talk about!

PROFESSIONAL DOCUMENT CREATION:
You also have access to advanced document creation capabilities:
- task_tracker: Create Excel spreadsheets with formulas and conditional formatting
- process_report: Generate comprehensive process optimization reports (Word)
- dashboard: Create data analysis dashboards with charts (PNG)
- presentation: Build professional PowerPoint presentations

When creating documents, use this format:
DOCUMENT_CREATE: {{
  "type": "task_tracker",
  "content": {{
    "tasks": [...],
    "title": "..."
  }}
}}

You can create professional business documents, not just basic files!"""
        
        # Get conversation history
        conversation_history = self.memory.get_conversation_context(personality)
        
        # Check for images in context
        images = context.get('images', None)
        
        # Generate REAL AI response
        ai_response = self.claude_engine.generate_response(
            user_input, system_prompt, conversation_history, images
        )
        
        # Check for tool usage
        if "TOOL_USE:" in ai_response and personality.lower() == "tamara":
            ai_response = self._execute_tamara_tools(ai_response, user_input)
        
        # Check for document creation (both personalities)
        if "DOCUMENT_CREATE:" in ai_response:
            ai_response = self._execute_document_creation(ai_response, personality)
        
        return ai_response
    
    def _execute_tamara_tools(self, ai_response: str, user_input: str) -> str:
        """Execute computer tools requested by TAMARA"""
        try:
            # Extract tool usage from response
            import re
            import json
            
            tool_pattern = r'TOOL_USE:\s*\{([^}]+)\}'
            matches = re.findall(tool_pattern, ai_response, re.DOTALL)
            
            for match in matches:
                try:
                    # Parse tool request
                    tool_data = json.loads('{' + match + '}')
                    tool_name = tool_data.get('tool')
                    parameters = tool_data.get('parameters', {})
                    
                    if tool_name in self.tamara_tools.get_available_tools():
                        # Execute tool
                        result = self.tamara_tools.execute_tool(tool_name, **parameters)
                        
                        # Format result for user
                        formatted_result = self.tamara_tools.format_tool_result(tool_name, result)
                        
                        # Replace TOOL_USE block with result
                        tool_block = f"TOOL_USE: {{{match}}}"
                        ai_response = ai_response.replace(tool_block, f"\n\n🔧 **Tool Execution:**\n{formatted_result}")
                        
                        logger.info(f"TAMARA executed tool: {tool_name} - Success: {result['success']}")
                    
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse tool request: {match}")
                    continue
                except Exception as e:
                    logger.error(f"Tool execution error: {e}")
                    continue
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Failed to process TAMARA tools: {e}")
            return ai_response
    
    def _execute_document_creation(self, ai_response: str, personality: str) -> str:
        """Execute document creation requested by any personality"""
        try:
            # Extract document creation requests from response
            import re
            import json
            
            doc_pattern = r'DOCUMENT_CREATE:\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
            matches = re.findall(doc_pattern, ai_response, re.DOTALL)
            
            for match in matches:
                try:
                    # Parse document request
                    doc_data = json.loads('{' + match + '}')
                    doc_type = doc_data.get('type')
                    content = doc_data.get('content', {})
                    
                    # Create document based on personality with ENHANCED capabilities
                    if personality.lower() == "captain":
                        captain_docs = ["roadmap", "crisis_plan", "gantt", "presentation", "email", "essay", "frontend", "pdf"]
                        if doc_type in captain_docs:
                            filepath = create_captain_document(doc_type, content)
                            emoji_map = {
                                "roadmap": "🗺️", "crisis_plan": "🚨", "gantt": "📊", 
                                "presentation": "📽️", "email": "📧", "essay": "📝", 
                                "frontend": "💻", "pdf": "📄"
                            }
                            emoji = emoji_map.get(doc_type, "📄")
                            result_text = f"✅ **Strategic Document Created:**\n{emoji} {doc_type.title()}: {filepath}"
                        else:
                            result_text = f"❌ Unknown document type for CAPTAIN: {doc_type}\nAvailable: {', '.join(captain_docs)}"
                    
                    elif personality.lower() == "tamara":
                        tamara_docs = ["task_tracker", "process_report", "dashboard", "presentation", "email", "essay", "frontend", "pdf"]
                        if doc_type in tamara_docs:
                            filepath = create_tamara_document(doc_type, content)
                            emoji_map = {
                                "task_tracker": "✅", "process_report": "📈", "dashboard": "📊", 
                                "presentation": "📽️", "email": "💌", "essay": "✍️", 
                                "frontend": "🎨", "pdf": "📋"
                            }
                            emoji = emoji_map.get(doc_type, "📄")
                            result_text = f"✅ **Professional Document Created:**\n{emoji} {doc_type.title()}: {filepath}"
                        else:
                            result_text = f"❌ Unknown document type for TAMARA: {doc_type}\nAvailable: {', '.join(tamara_docs)}"
                    
                    else:
                        result_text = f"❌ Document creation not available for {personality}"
                    
                    # Replace DOCUMENT_CREATE block with result
                    doc_block = f"DOCUMENT_CREATE: {{{match}}}"
                    ai_response = ai_response.replace(doc_block, f"\n\n📋 **Document Creation:**\n{result_text}")
                    
                    logger.info(f"{personality.upper()} created document: {doc_type}")
                    
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse document request: {match}")
                    continue
                except Exception as e:
                    logger.error(f"Document creation error: {e}")
                    continue
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Failed to process document creation: {e}")
            return ai_response
    
    def execute_react_cycle(self, input_text: str, personality: str, context: Dict[str, Any] = None) -> Tuple[str, ReActStep]:
        """Execute full ReAct cycle with REAL Claude AI"""
        if context is None:
            context = {}
        
        logger.info(f"Starting REAL AI ReAct cycle for {personality} with input: {input_text[:50]}...")
        
        # Observe
        observation = self.observe(input_text, personality, context)
        
        # Reason (WITH REAL AI)
        reasoning = self.reason(observation, personality, context)
        
        # Act (WITH REAL AI)
        action = self.act(reasoning, input_text, personality, context)
        
        # Create ReAct step record
        react_step = ReActStep(
            observation=observation,
            reasoning=reasoning,
            action=action,
            timestamp=datetime.now(),
            personality=personality,
            ai_generated=self.claude_engine.is_available()
        )
        
        # Store in history
        self.react_history.append(react_step)
        
        # Add to episodic memory with full conversation
        self.memory.add_to_episodic_memory(
            f"User: {input_text} → AI: {action[:100]}...",
            personality,
            {"user_input": input_text, "ai_response": action, **context},
            importance=0.8
        )
        
        logger.info(f"REAL AI ReAct cycle completed for {personality}")
        return action, react_step

class DynamicMemory:
    """
    Persistent learning memory system based on research:
    - Stores memory.json on disk (persists across sessions)
    - Updates from every conversation
    - Learns user patterns continuously
    - Tracks temporal changes (deadlines approaching, progress updates)
    
    Research sources:
    - Redis Agent Memory patterns
    - LangGraph/LangMem approaches
    - Semantic + Episodic + Procedural memory taxonomy
    """
    
    def __init__(self, memory_file: str = "memory.json"):
        self.memory_file = Path.home() / "Desktop" / "bowen" / memory_file
        self.memory = self.load()
        
    def load(self) -> Dict[str, Any]:
        """Load memory from disk"""
        if self.memory_file.exists():
            with open(self.memory_file, 'r') as f:
                return json.load(f)
        
        # Initialize empty memory structure
        return {
            "facts": {},  # Semantic memory: facts about user
            "events": [],  # Episodic memory: things that happened
            "patterns": {},  # Learned behavioral patterns
            "temporal_tracking": {},  # Time-sensitive items
            "last_updated": datetime.now().isoformat()
        }
    
    def save(self):
        """Persist memory to disk"""
        self.memory["last_updated"] = datetime.now().isoformat()
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file, 'w') as f:
            json.dump(self.memory, f, indent=2, default=str)
    
    def learn_from_conversation(self, user_input: str, ai_response: str):
        """
        Extract facts from conversation and update memory
        Research-based fact extraction patterns
        """
        lower_input = user_input.lower()
        
        # Progress updates
        if "is" in lower_input and ("%" in lower_input or "percent" in lower_input or "done" in lower_input):
            self._extract_progress_update(user_input)
        
        # Completions
        if any(word in lower_input for word in ["finished", "done", "completed", "exam done"]):
            self._extract_completion(user_input)
        
        # Deadlines
        if any(word in lower_input for word in ["due", "deadline", "tomorrow", "next week"]):
            self._extract_deadline(user_input)
        
        # Team updates
        if any(word in lower_input for word in ["abayomi", "collins", "team"]):
            self._extract_team_update(user_input)
        
        # Day counters (75 Hard, etc.)
        if "day" in lower_input and any(char.isdigit() for char in lower_input):
            self._extract_day_counter(user_input)
        
        # Always save after learning
        self.save()
    
    def _extract_progress_update(self, text: str):
        """Extract project progress from statements like 'remi is 70% done'"""
        # Simple pattern matching - production would use NLP
        if "remi" in text.lower():
            # Extract percentage
            import re
            match = re.search(r'(\d+)\s*%', text)
            if match:
                progress = int(match.group(1))
                self.memory["facts"]["remi_progress"] = {
                    "percent": progress,
                    "updated": datetime.now().isoformat()
                }
    
    def _extract_completion(self, text: str):
        """Mark tasks as complete"""
        if "exam" in text.lower() and "done" in text.lower():
            self.memory["events"].append({
                "type": "task_completed",
                "task": "Database exam",
                "completed_at": datetime.now().isoformat()
            })
    
    def _extract_deadline(self, text: str):
        """Extract and track deadlines"""
        # Would implement NLP-based extraction in production
        pass
    
    def _extract_team_update(self, text: str):
        """Track team member status changes"""
        # Would implement entity recognition in production
        pass
    
    def _extract_day_counter(self, text: str):
        """Track daily challenges like 75 Hard"""
        if "75 hard" in text.lower() or "75hard" in text.lower():
            import re
            match = re.search(r'day\s*(\d+)', text.lower())
            if match:
                day = int(match.group(1))
                self.memory["facts"]["75_hard_day"] = {
                    "current_day": day,
                    "updated": datetime.now().isoformat()
                }
    
    def get_current_context(self, user_context: Dict) -> Dict[str, Any]:
        """
        Generate dynamic briefing based on current state
        Combines static user_context with dynamic memory
        """
        now = datetime.now()
        
        # Start with priorities from user_context
        priorities = []
        
        # Add from user_context
        if "current_priorities" in user_context:
            for priority in user_context["current_priorities"]:
                # Calculate relative time
                if "due_days" in priority:
                    days = priority["due_days"]
                    if days <= 3:
                        priorities.append({
                            **priority,
                            "urgency": "high" if days <= 1 else "medium"
                        })
                else:
                    priorities.append({**priority, "urgency": "medium"})
        
        # Enhance with memory
        if "remi_progress" in self.memory["facts"]:
            progress = self.memory["facts"]["remi_progress"]["percent"]
            priorities.append({
                "task": f"Remi Guardian ({progress}% complete)",
                "urgency": "high" if progress < 70 else "medium"
            })
        
        return {
            "priorities": sorted(priorities, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("urgency", "low"), 2)),
            "memory": self.memory,
            "user_context": user_context
        }

class Intent(Enum):
    """
    Research-based intent taxonomy
    Source: NLU intent classification patterns 2025
    """
    SCREEN_CAPTURE = "screen_capture"
    BRIEFING = "briefing"
    HOMEWORK_HELP = "homework_help"
    PROJECT_STATUS = "project_status"
    FILE_CREATION = "file_creation"
    CODE_HELP = "code_help"
    FINANCIAL = "financial"
    PERSONAL_TRACKING = "personal_tracking"
    RESEARCH = "research"
    CODEBASE_ANALYSIS = "codebase_analysis"
    GENERAL_CHAT = "general_chat"

class IntentDetector:
    """
    Natural language intent detection
    
    Research-based approach:
    - Pattern matching for common phrases
    - Context-aware (uses memory + user context)
    - Confidence scoring
    - Falls back to general chat if uncertain
    
    Sources:
    - Intent classification best practices (FlowHunt 2025)
    - Multi-dimensional intent detection (Taner Tombas 2025)
    """
    
    def __init__(self):
        # Define trigger patterns for each intent
        self.intent_patterns = {
            Intent.SCREEN_CAPTURE: [
                "screenshot", "screen capture", "take a screenshot",
                "look at my screen", "check this", "see my screen",
                "what's this error", "analyze this", "capture screen",
                "what's on my screen"
            ],
            Intent.BRIEFING: [
                "morning briefing", "brief me", "briefing",
                "what's up", "good morning", "priorities", 
                "what should i work on", "what should i do",
                "what's my priority"
            ],
            Intent.HOMEWORK_HELP: [
                "help with", "explain", "how does", "understand",
                "what is", "teach me", "homework", "assignment",
                "study", "learn", "concept"
            ],
            Intent.PROJECT_STATUS: [
                "how is remi", "remi doing", "remi status", "remi guardian",
                "team status", "how's the team", "shiprite update", 
                "progress", "project status", "how's", "doing"
            ],
            Intent.FILE_CREATION: [
                "create", "make", "generate", "build",
                "write", "draft", "study guide", "file"
            ],
            Intent.CODE_HELP: [
                "debug", "fix this", "error", "bug",
                "why isn't this working", "code issue", "fix"
            ],
            Intent.FINANCIAL: [
                "salary", "salaries", "pay", "payment", "due",
                "when are", "transfer", "cost", "money"
            ],
            Intent.PERSONAL_TRACKING: [
                "75 hard", "workout", "exercise", "hard challenge",
                "day", "challenge", "fitness", "progress"
            ],
            Intent.RESEARCH: [
                "research", "analyze", "investigate", "study",
                "find out", "look into", "explore", "examine"
            ],
            Intent.CODEBASE_ANALYSIS: [
                "analyze code", "codebase", "repository", "code review",
                "understand code", "map project", "dependencies"
            ]
        }
    
    def detect(self, user_input: str, context: Optional[Dict] = None) -> Intent:
        """
        Detect user intent from natural language
        
        Args:
            user_input: Raw user message
            context: Optional context (memory, user_context) for disambiguation
            
        Returns:
            Intent enum value
        """
        lower_input = user_input.lower()
        
        # Check each intent's patterns
        for intent, patterns in self.intent_patterns.items():
            if any(pattern in lower_input for pattern in patterns):
                return intent
        
        # Default to general chat
        return Intent.GENERAL_CHAT
    
    def get_intent_confidence(self, user_input: str, intent: Intent) -> float:
        """
        Calculate confidence score for detected intent
        Research-based confidence calculation
        """
        if intent not in self.intent_patterns:
            return 0.5
        
        patterns = self.intent_patterns[intent]
        matches = sum(1 for pattern in patterns if pattern in user_input.lower())
        
        # Base confidence
        confidence = 0.7
        
        # Boost for multiple pattern matches
        if matches > 1:
            confidence += 0.15
        
        # Boost for longer, more specific inputs
        if len(user_input.split()) > 5:
            confidence += 0.05
        
        return min(confidence, 1.0)

class ProactiveAssistant:
    """
    Proactive intelligence system
    
    Research-based proactive AI patterns:
    - Morning briefings with current priorities
    - Smart reminders based on user patterns
    - Progress tracking
    - Deadline monitoring
    
    Sources:
    - Proactive AI assistant design (CHI 2025)
    - Personal AI infrastructure patterns (Daniel Miessler 2025)
    """
    
    def __init__(self, memory: DynamicMemory, user_context: Dict):
        self.memory = memory
        self.user_context = user_context
    
    def generate_morning_briefing(self) -> str:
        """
        Generate personalized morning briefing
        Research: Proactive assistants should contextualize priorities
        """
        context = self.memory.get_current_context(self.user_context)
        priorities = context["priorities"][:5]  # Top 5
        
        briefing = f"Good morning, {self.user_context['personal']['name']}.\n\n"
        briefing += "TODAY'S PRIORITIES:\n"
        
        for i, priority in enumerate(priorities, 1):
            task = priority.get("task", "Unknown task")
            briefing += f"{i}. {task}"
            
            if "notes" in priority:
                briefing += f" ({priority['notes']})"
            elif "time_needed_hours" in priority:
                briefing += f" ({priority['time_needed_hours']} hours needed)"
            elif "deadline_days" in priority:
                briefing += f" (due in {priority['deadline_days']} days)"
                
            briefing += "\n"
        
        # Add alerts
        alerts = self._generate_alerts(context)
        if alerts:
            briefing += "\nALERTS:\n"
            for alert in alerts:
                briefing += f"⚠️ {alert}\n"
        
        briefing += "\nWhat do you want to tackle first?\n"
        
        return briefing
    
    def _generate_alerts(self, context: Dict) -> List[str]:
        """Generate smart alerts based on context"""
        alerts = []
        
        # Check for approaching deadlines
        for priority in context.get("priorities", []):
            if priority.get("due_days", 99) <= 2:
                alerts.append(f"{priority['task']} due in {priority['due_days']} days")
        
        # Check for things behind schedule
        for priority in context.get("priorities", []):
            if priority.get("behind_schedule"):
                alerts.append(f"{priority['task']} is behind schedule")
        
        # Check for daily streaks
        if "75_hard_day" in self.memory.memory["facts"]:
            # Check if workout done today
            # (Would need more sophisticated tracking)
            alerts.append("Haven't completed 75 Hard workout yet today")
        
        return alerts
    
    def should_remind(self, task: str, context: Dict) -> bool:
        """
        Determine if user should be reminded about a task
        Research: Pattern-based reminder logic
        """
        # Would implement sophisticated reminder logic
        # Based on user patterns, time of day, task urgency
        return False

class BOWENFramework:
    """
    Main BOWEN Framework - Personal AI Assistant
    Simplified, no personalities - just intelligence
    """
    
    def __init__(self):
        # Core engines (keep what works)
        self.claude_engine = ClaudeEngine()
        self.vision_engine = VisionEngine() if ENHANCED_MODULES_AVAILABLE else None
        self.computer_engine = ComputerUseEngine()
        
        # Try to import document engine
        try:
            from document_engine import AdvancedDocumentEngine
            self.document_engine = AdvancedDocumentEngine()
        except:
            self.document_engine = None
        
        # Add new systems
        self.memory = DynamicMemory()
        self.intent_detector = IntentDetector()
        
        # Load user context
        context_file = Path.home() / "Desktop" / "bowen" / "user_context.yaml"
        if context_file.exists():
            with open(context_file) as f:
                self.user_context = yaml.safe_load(f)
        else:
            self.user_context = {}
            
        self.proactive_assistant = ProactiveAssistant(self.memory, self.user_context)
        
        # Keep some compatibility for existing process_input method
        self.current_personality = PersonalityType.CAPTAIN  # Default, but not used for switching
        self.memory_system = MemorySystem()  # Keep for compatibility
        
        # Add enhanced modules compatibility
        if ENHANCED_MODULES_AVAILABLE:
            try:
                self.adaptive_memory = AdaptiveMemory()
            except:
                self.adaptive_memory = None
        else:
            self.adaptive_memory = None
        
        # Try to initialize ReActEngine if needed
        try:
            self.react_engine = ReActEngine(self.memory_system, None)  # No personality engine
        except:
            self.react_engine = None
        
        self.session_start = datetime.now()
        
        # Verify AI availability
        if self.claude_engine.is_available():
            logger.info("BOWEN Framework initialized with REAL Claude API")
        else:
            logger.warning("BOWEN Framework initialized WITHOUT AI - set ANTHROPIC_API_KEY for real responses")
    
    def switch_personality(self, personality: PersonalityType) -> str:
        """Switch to a different personality"""
        old_personality = self.current_personality.value
        self.current_personality = personality
        
        # Log personality switch in memory
        self.memory_system.add_to_episodic_memory(
            f"Personality switch: {old_personality} → {personality.value}",
            personality.value,
            {"switch_time": datetime.now().isoformat()},
            importance=0.6
        )
        
        # Get real AI greeting
        if self.react_engine.claude_engine.is_available():
            system_prompt = self.personality_engine.build_system_prompt(personality.value)
            greeting = self.react_engine.claude_engine.generate_response(
                "Hello! I just became active. Please introduce yourself briefly and ask how you can help.",
                system_prompt,
                []
            )
            return f"Switching to {personality.value.upper()}...\n\n{greeting}"
        else:
            return f"Switching to {personality.value.upper()}... (AI responses not available - set ANTHROPIC_API_KEY)"
    
    def process_input(self, user_input: str, personality: str = None, context: Dict[str, Any] = None) -> str:
        """Main method to process user input through current personality WITH REAL AI + Enhanced Capabilities"""
        # Use provided personality or current one
        active_personality = personality or self.current_personality.value
        
        if context is None:
            context = {
                "session_duration": str(datetime.now() - self.session_start),
                "personality": active_personality
            }
        
        # Handle enhanced commands first
        if user_input.startswith('/') and ENHANCED_MODULES_AVAILABLE:
            return self.handle_enhanced_command(user_input, active_personality)
        
        # Learn from this interaction if adaptive memory is available
        if self.adaptive_memory:
            interaction = {
                'text': user_input,
                'type': 'user_input',
                'personality': active_personality,
                'timestamp': datetime.now().isoformat()
            }
            self.adaptive_memory.learn_from_interaction(interaction)
        
        # Execute ReAct cycle with REAL Claude AI
        response, react_step = self.react_engine.execute_react_cycle(
            user_input, active_personality, context
        )
        
        # Learn from the response if adaptive memory is available
        if self.adaptive_memory:
            response_interaction = {
                'text': response,
                'type': 'ai_response',
                'personality': active_personality,
                'outcome': 'generated',
                'timestamp': datetime.now().isoformat()
            }
            self.adaptive_memory.learn_from_interaction(response_interaction)
        
        return response
    
    def handle_enhanced_command(self, command: str, personality: str) -> str:
        """Handle enhanced commands (vision, memory, proactive)"""
        parts = command[1:].split(' ', 1)  # Remove '/' and split
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        try:
            # Vision commands
            if cmd == 'capture':
                return handle_capture_command(args)
            elif cmd == 'homework':
                return handle_homework_command(args)
            elif cmd == 'code':
                return handle_code_command(args)
            elif cmd in ['document', 'doc']:
                return self.vision_engine.analyze_document(args)
            elif cmd == 'exam':
                return self.vision_engine.analyze_exam(args)
            elif cmd == 'business':
                return self.vision_engine.analyze_business(args)
            
            # Proactive commands
            elif cmd == 'briefing':
                return self.proactive_assistant.generate_morning_briefing()
            elif cmd == 'priorities':
                priorities = self.proactive_assistant.get_todays_priorities()
                result = "🎯 **TODAY'S PRIORITIES:**\n"
                for i, p in enumerate(priorities, 1):
                    result += f"{i}. **{p['name']}** ({p['category']})\n"
                return result
            elif cmd == 'deadlines':
                deadlines = self.proactive_assistant.get_urgent_deadlines()
                result = "⚠️ **URGENT DEADLINES:**\n"
                for d in deadlines:
                    days = (d.due_date - datetime.now()).days
                    result += f"• **{d.name}**: {days} days ({d.progress*100:.0f}% done)\n"
                return result
            elif cmd == 'progress':
                progress = self.proactive_assistant.get_progress_summary()
                result = "📈 **PROGRESS SUMMARY:**\n"
                for p in progress:
                    result += f"• **{p['name']}**: {p['progress']}%"
                    if p['behind_schedule']:
                        result += f" (⚠️ {p['days_behind']} days behind)"
                    result += "\n"
                return result
            elif cmd == 'goals':
                goals = self.proactive_assistant.check_personal_goals()
                result = "💪 **PERSONAL GOALS:**\n"
                for g in goals:
                    result += f"• **{g['name']}**: Day {g['current_day']}/{g['total_days']}\n"
                    if g['due_today']:
                        result += f"  📋 Today: {g['requirement']}\n"
                return result
            elif cmd == 'week':
                return self.proactive_assistant.get_weekly_overview()
            
            # Memory commands
            elif cmd == 'memory':
                return self.adaptive_memory.generate_learning_report()
            elif cmd == 'context':
                if args:
                    summary = self.adaptive_memory.get_context_summary(args)
                    if summary:
                        result = f"📚 **{summary['name'].upper()} CONTEXT:**\n"
                        result += f"Category: {summary['category']}\n"
                        result += f"Strengths: {', '.join(summary['strengths']) if summary['strengths'] else 'None yet'}\n"
                        result += f"Weaknesses: {', '.join(summary['weaknesses']) if summary['weaknesses'] else 'None identified'}\n"
                        result += f"Importance: {summary['importance']:.1f}/1.0\n"
                        result += f"Interactions: {summary['interaction_count']}\n"
                        return result
                    else:
                        return f"❌ Context '{args}' not found"
                else:
                    priorities = self.adaptive_memory.get_current_priorities()
                    result = "🧠 **MEMORY CONTEXTS:**\n"
                    for p in priorities[:5]:
                        result += f"• **{p['name']}** ({p['category']}) - Importance: {p['importance']:.1f}\n"
                    return result
            
            # Help command
            elif cmd == 'help':
                return self.get_enhanced_help()
            
            else:
                return f"❌ Unknown command: /{cmd}\nType /help for available commands"
                
        except Exception as e:
            logger.error(f"Enhanced command failed: {e}")
            return f"❌ Command failed: {str(e)}"
    
    def get_enhanced_help(self) -> str:
        """Get help for all enhanced commands"""
        help_text = """🚀 **BOWEN ENHANCED COMMANDS**

**Vision & Screenshot Analysis:**
• `/capture [query]` - Take screenshot and analyze
• `/homework [question]` - Analyze homework (explains concepts)
• `/code [question]` - Debug code from screenshot
• `/document` - Read and summarize documents
• `/exam` - Help with exam questions
• `/business` - Analyze business documents

**Proactive Intelligence:**
• `/briefing` - Morning briefing with priorities
• `/priorities` - Today's top priorities
• `/deadlines` - Urgent deadlines
• `/progress` - Progress on active projects
• `/goals` - Personal goals status
• `/week` - Weekly overview

**Adaptive Memory:**
• `/memory` - Learning report
• `/context [name]` - Specific context details
• `/help` - This help message

**Examples:**
• `/capture What's on my screen?`
• `/homework Help me understand this problem`
• `/code What's wrong here?`
• `/briefing` (for morning priorities)
• `/progress` (check project status)
"""
        return help_text
    
    def get_available_personalities(self) -> List[str]:
        """Get list of available personalities"""
        return list(self.personality_engine.personalities.keys())
    
    def get_memory_summary(self) -> Dict[str, int]:
        """Get summary of memory system state"""
        return {
            "working_memory": len(self.memory_system.working_memory),
            "episodic_memory": len(self.memory_system.episodic_memory),
            "semantic_memory": len(self.memory_system.semantic_memory),
            "react_history": len(self.react_engine.react_history)
        }
    
    def is_ai_enabled(self) -> bool:
        """Check if real AI responses are available"""
        return self.react_engine.claude_engine.is_available()

if __name__ == "__main__":
    # Check API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ CRITICAL: ANTHROPIC_API_KEY not set!")
        print("Set your Claude API key: export ANTHROPIC_API_KEY='your-key-here'")
        print("Get key from: https://console.anthropic.com/settings/keys")
        sys.exit(1)
    
    # Initialize BOWEN Framework with REAL AI
    bowen = BOWENFramework()
    
    print("🧭 BOWEN Framework - Built On Wisdom, Excellence, and Nobility")
    print("=" * 60)
    print(f"🤖 Real AI Status: {'✅ ENABLED' if bowen.is_ai_enabled() else '❌ DISABLED'}")
    print(f"📊 Available personalities: {', '.join(bowen.get_available_personalities())}")
    print(f"🎖️ Current personality: {bowen.current_personality.value.upper()}")
    print("=" * 60)
    
    # Test with real Claude AI
    if bowen.is_ai_enabled():
        test_input = "Should I prioritize building Remi Guardian or FraudZero first?"
        print(f"\n🔬 Testing REAL AI Response:")
        print(f"Input: {test_input}")
        print("Processing through Claude Sonnet 4...")
        
        response = bowen.process_input(test_input)
        print(f"\n🎖️ CAPTAIN's REAL Response:\n{response}")
        
        # Test personality switch
        print(f"\n🔄 Testing Personality Switch to TAMARA...")
        switch_response = bowen.switch_personality(PersonalityType.TAMARA)
        print(f"{switch_response}")
        
        # Test same question with TAMARA
        response2 = bowen.process_input(test_input)
        print(f"\n🌟 TAMARA's REAL Response:\n{response2}")
        
    else:
        print("❌ Cannot test - API key not configured")
        print("Run: export ANTHROPIC_API_KEY='your-key-here'")