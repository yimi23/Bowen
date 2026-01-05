#!/usr/bin/env python3
"""
JARVIS - Personal AI Assistant for Praise Oyimi
Natural language interface with proactive intelligence
"""

import os
import sys
import yaml
import re
from datetime import datetime, timedelta
from pathlib import Path

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import existing working components
from claude_engine import ClaudeEngine
from vision_engine import VisionEngine
from computer_use_engine import ComputerUseEngine

class IntentDetector:
    """Detects user intent from natural language input"""
    
    def __init__(self, user_context):
        self.context = user_context
        
    def detect_intent(self, user_input: str) -> str:
        """Analyze user input and return detected intent"""
        input_lower = user_input.lower()
        
        # Screen capture intent
        screen_phrases = [
            "look at my screen", "see my screen", "check my screen",
            "what's this error", "analyze this", "check this code",
            "look at this", "see this", "debug this"
        ]
        if any(phrase in input_lower for phrase in screen_phrases):
            return "screen_capture"
            
        # Briefing intent
        briefing_phrases = [
            "what should i work on", "what's my priority", "what's up",
            "what do i need to do", "what's today", "morning briefing",
            "what's important", "what's urgent", "priorities"
        ]
        if any(phrase in input_lower for phrase in briefing_phrases):
            return "briefing"
            
        # Teaching/homework help intent
        teaching_phrases = [
            "help me with", "explain", "how does", "what is",
            "teach me", "understand", "clarify", "confused about",
            "normalization", "database", "study", "homework"
        ]
        if any(phrase in input_lower for phrase in teaching_phrases):
            return "teaching"
            
        # Business intelligence intent
        business_phrases = [
            "how's remi", "team status", "shiprite", "business",
            "revenue", "users", "salary", "payment", "collins",
            "abayomi", "developer", "team"
        ]
        if any(phrase in input_lower for phrase in business_phrases):
            return "business"
            
        # File creation intent
        creation_phrases = [
            "create", "make", "generate", "write", "build",
            "study guide", "document", "file", "notes"
        ]
        if any(phrase in input_lower for phrase in creation_phrases):
            return "create_file"
            
        # Personal management intent
        personal_phrases = [
            "workout", "75 hard", "schedule", "remind",
            "what should i do", "tonight", "today"
        ]
        if any(phrase in input_lower for phrase in personal_phrases):
            return "personal_management"
            
        # Default to general chat
        return "general_chat"

class JARVIS:
    """Personal AI Assistant for Praise Oyimi"""
    
    def __init__(self):
        print("Initializing JARVIS...")
        
        # Load user context
        self.load_user_context()
        
        # Initialize engines
        self.claude = ClaudeEngine()
        self.vision = VisionEngine()
        self.computer = ComputerUseEngine()
        self.intent_detector = IntentDetector(self.user_context)
        
        # Setup outputs directory
        self.outputs_dir = Path.home() / "Desktop" / "bowen_outputs"
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        
        print("✅ JARVIS ready")
        
    def load_user_context(self):
        """Load Praise's personal context"""
        try:
            with open("user_context.yaml", "r") as f:
                self.user_context = yaml.safe_load(f)
        except FileNotFoundError:
            print("⚠️ user_context.yaml not found. Using minimal context.")
            self.user_context = {"user": {"name": "Praise"}}
    
    def show_morning_briefing(self):
        """Show proactive morning briefing"""
        context = self.user_context
        user_name = context.get("user", {}).get("name", "Praise")
        
        print(f"\nGood morning, {user_name}.")
        print("TODAY'S PRIORITIES:")
        
        # Show urgent tasks
        priorities = context.get("current_priorities", {})
        
        if "urgent" in priorities:
            for task in priorities["urgent"]:
                if isinstance(task, dict):
                    print(f"🔴 {task.get('task', 'Unknown task')} - {task.get('status', '')}")
                    
        if "today" in priorities:
            for task in priorities["today"]:
                if isinstance(task, dict):
                    status_indicator = "⚠️" if task.get("behind_schedule") or task.get("warning") else "📋"
                    print(f"{status_indicator} {task.get('task', 'Unknown task')} - {task.get('status', '')}")
        
        # Show alerts
        print("\nALERTS:")
        if "this_week" in priorities:
            for task in priorities["this_week"]:
                if isinstance(task, dict) and task.get("due") == "2 days":
                    print(f"⚠️ {task.get('task', 'Unknown task')} due in {task.get('due')} ({task.get('amount', '')})")
        
        # Check for overdue items
        remi = context.get("companies", {}).get("remi_guardian", {})
        if remi.get("behind_schedule"):
            print(f"⚠️ Remi is behind schedule ({remi.get('current_progress', 'unknown')} complete)")
            
        print("\nReady to go?\n")
    
    def handle_screen_capture(self, user_input: str) -> str:
        """Capture screen and analyze with Claude Vision"""
        try:
            print("📸 Capturing screen...")
            
            # Capture screen
            image_data = self.vision.capture_screen(save_file=True)
            
            # Analyze with Claude Vision
            analysis_prompt = f"""
            Analyze this screenshot. The user said: "{user_input}"
            
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
            
            response = self.vision.analyze_with_claude(
                image_data=image_data,
                prompt=analysis_prompt,
                context="screen_analysis"
            )
            
            return response
            
        except Exception as e:
            return f"Sorry, couldn't capture screen: {str(e)}"
    
    def handle_briefing(self) -> str:
        """Generate personalized briefing"""
        context = self.user_context
        
        briefing_prompt = f"""
        Give Praise a personalized briefing based on his current situation:
        
        CONTEXT:
        - 22-year-old CMU student, CEO of ShipRite
        - Database exam today at 2pm (weak on normalization)
        - Building Remi Guardian (behind schedule, needs whiteboard feature)
        - 75 Hard challenge Day 24/75 (hasn't worked out today)
        - DePaul grad school application 30% done (due in 15 days)
        - Team salaries due in 2 days (320K NGN)
        
        CURRENT TIME: {datetime.now().strftime('%I:%M %p')}
        
        Give him a smart, friendly briefing. What should he focus on right now?
        Be specific and actionable. Talk like a smart friend, not a formal assistant.
        """
        
        response = self.claude.generate_response(
            prompt=briefing_prompt,
            context="personal_briefing"
        )
        
        return response
    
    def handle_teaching(self, user_input: str) -> str:
        """Provide educational guidance without giving direct answers"""
        
        teaching_prompt = f"""
        Praise needs help with: "{user_input}"
        
        CONTEXT:
        - 22-year-old CMU student studying Information Technology
        - Has Database Systems exam today at 2pm
        - Weak on normalization (3NF, functional dependencies)
        - Wants to understand concepts, not just get answers
        
        TEACHING GUIDELINES:
        ✅ Explain concepts clearly
        ✅ Ask guiding questions
        ✅ Point out common mistakes
        ✅ Help him think through problems
        ✅ Use examples he can relate to
        
        ❌ Don't give direct homework answers
        ❌ Don't do the work for him
        ❌ Don't be overly formal
        
        Respond as a smart study buddy who wants him to actually learn.
        """
        
        response = self.claude.generate_response(
            prompt=teaching_prompt,
            context="teaching"
        )
        
        return response
    
    def handle_business_query(self, user_input: str) -> str:
        """Handle business intelligence queries"""
        context = self.user_context
        
        business_prompt = f"""
        Praise asked: "{user_input}"
        
        BUSINESS CONTEXT:
        
        ShipRite (Product Studio):
        - CEO/Founder, 8-person team
        - Key team: Abayomi (Lead Engineer, 145K NGN/mo), Collins (Designer, 75K NGN/mo), Developer (100K NGN/mo)
        - Monthly salary cost: 320K NGN
        - Salaries due in 2 days
        
        Remi Guardian (AI Study Assistant):
        - Launching January 2026
        - Target: 2,381 users by March 2026
        - Revenue goal: $6,250/month
        - Praise's share: 25% of 70% ≈ $11K/month
        - Currently 60% complete
        - Behind schedule on whiteboard feature
        
        Other projects: FraudZero, FlickChoice, Bible Path, Twine Campus
        
        Give a business-focused response. Be concise and actionable.
        """
        
        response = self.claude.generate_response(
            prompt=business_prompt,
            context="business"
        )
        
        return response
    
    def handle_file_creation(self, user_input: str) -> str:
        """Create files based on user request"""
        
        creation_prompt = f"""
        Praise wants: "{user_input}"
        
        CONTEXT:
        - CMU Information Technology student
        - Database Systems exam today (needs normalization help)
        - Building Remi Guardian app
        - 75 Hard fitness challenge
        - DePaul grad application in progress
        
        Create the requested file. Make it useful and specific to his needs.
        Save it to ~/Desktop/bowen_outputs/
        
        What should I create and what should be in it?
        """
        
        # Get creation plan from Claude
        plan_response = self.claude.generate_response(
            prompt=creation_prompt,
            context="file_creation_plan"
        )
        
        # For now, create a simple file - in a real implementation you'd parse the plan
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"created_content_{timestamp}.md"
        filepath = self.outputs_dir / filename
        
        try:
            with open(filepath, "w") as f:
                f.write(f"# Created Content\n\n")
                f.write(f"Request: {user_input}\n\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(plan_response)
            
            return f"Created {filename} in bowen_outputs. {plan_response[:100]}..."
            
        except Exception as e:
            return f"Sorry, couldn't create file: {str(e)}"
    
    def handle_personal_management(self, user_input: str) -> str:
        """Handle personal scheduling and life management"""
        context = self.user_context
        
        personal_prompt = f"""
        Praise asked: "{user_input}"
        
        PERSONAL CONTEXT:
        - Database exam today at 2pm
        - 75 Hard Day 24/75 (hasn't worked out yet)
        - Behind on Remi development
        - DePaul essay needs work
        - Typical workout time: 8pm
        
        CURRENT TIME: {datetime.now().strftime('%I:%M %p')}
        
        Give him smart personal advice. Consider his priorities, energy, and deadlines.
        Be like a smart friend who knows his life and goals.
        """
        
        response = self.claude.generate_response(
            prompt=personal_prompt,
            context="personal_management"
        )
        
        return response
    
    def handle_general_chat(self, user_input: str) -> str:
        """Handle general conversation"""
        
        chat_prompt = f"""
        Praise said: "{user_input}"
        
        You're JARVIS, Praise's personal AI assistant. You know everything about his life:
        - 22-year-old CMU student, CEO of ShipRite
        - Building Remi Guardian AI study assistant
        - Database exam today, 75 Hard challenge, grad school applications
        - Nigerian heritage, wants to be Governor of Delta State someday
        
        Respond naturally, like a smart friend who knows his context.
        Be helpful, conversational, and aware of his situation.
        """
        
        response = self.claude.generate_response(
            prompt=chat_prompt,
            context="general"
        )
        
        return response
    
    def process_input(self, user_input: str) -> str:
        """Process user input and route to appropriate handler"""
        
        # Detect intent
        intent = self.intent_detector.detect_intent(user_input)
        
        # Route to appropriate handler
        if intent == "screen_capture":
            return self.handle_screen_capture(user_input)
        elif intent == "briefing":
            return self.handle_briefing()
        elif intent == "teaching":
            return self.handle_teaching(user_input)
        elif intent == "business":
            return self.handle_business_query(user_input)
        elif intent == "create_file":
            return self.handle_file_creation(user_input)
        elif intent == "personal_management":
            return self.handle_personal_management(user_input)
        else:
            return self.handle_general_chat(user_input)
    
    def run(self):
        """Main conversation loop"""
        
        # Show morning briefing
        self.show_morning_briefing()
        
        # Main conversation loop
        while True:
            try:
                # Simple, clean input
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                    
                # Handle quit
                if user_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                    print("Talk soon, Praise. 👋")
                    break
                
                # Process input and get response
                response = self.process_input(user_input)
                
                # Clean output
                print(f"AI: {response}\n")
                
            except EOFError:
                print("\nTalk soon, Praise. 👋")
                break
            except KeyboardInterrupt:
                print("\nTalk soon, Praise. 👋")
                break
            except Exception as e:
                print(f"Sorry, something went wrong: {str(e)}\n")

def main():
    """Main entry point"""
    try:
        jarvis = JARVIS()
        jarvis.run()
    except Exception as e:
        print(f"Failed to start JARVIS: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()