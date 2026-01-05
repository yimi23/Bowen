#!/usr/bin/env python3
"""
BOWEN - Simple, Real, No Bullshit
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from research_engine import ResearchEngine
import anthropic

class BOWEN:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.model = "claude-3-haiku-20240307"
        self.research_engine = ResearchEngine()
        
        # Load your actual context
        import yaml
        context_file = Path.home() / "Desktop" / "bowen" / "user_context.yaml"
        if context_file.exists():
            with open(context_file) as f:
                self.user_context = yaml.safe_load(f)
        else:
            self.user_context = {"personal": {"name": "Praise"}}
    
    def process(self, user_input: str) -> str:
        """Process whatever you ask - no fake categories or bullshit"""
        current_time = datetime.now()
        
        system_prompt = f"""You are THE CAPTAIN - {self.user_context['personal']['name']}'s personal assistant.

REAL CONTEXT:
- Current time: {current_time.strftime('%A, %B %d, %Y at %I:%M %p')}
- You are Praise's personal AI assistant
- Be direct, helpful, and real
- Don't make up fake priorities or alerts
- If you need to take a screenshot, capture screen, analyze code, research something, or create files - just do it

Respond naturally as The Captain. Be helpful without the fake dramatic briefings."""

        try:
            # Check if user wants specific capabilities
            if any(word in user_input.lower() for word in ['screen', 'screenshot', 'look at my']):
                return self.handle_screen_capture(user_input)
            elif any(word in user_input.lower() for word in ['research', 'analyze', 'investigate']):
                return self.research_engine.research_and_report(user_input)
            elif any(word in user_input.lower() for word in ['create', 'make', 'generate']):
                return self.handle_file_creation(user_input)
            else:
                # Just talk normally
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_input}]
                )
                return response.content[0].text
        except Exception as e:
            return f"Error: {e}"
    
    def handle_screen_capture(self, query: str) -> str:
        """Real screen capture"""
        try:
            from vision_engine import VisionEngine
            vision = VisionEngine()
            image_data = vision.capture_screen(save_file=True)
            analysis = vision.analyze_with_vision(image_data, query, "general")
            return analysis
        except Exception as e:
            return f"Screen capture failed: {e}"
    
    def handle_file_creation(self, query: str) -> str:
        """Real file creation"""
        try:
            outputs_dir = Path.home() / "Desktop" / "bowen_outputs"
            outputs_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"file_{timestamp}.md"
            filepath = outputs_dir / filename
            
            content = f"# File created at {datetime.now()}\n\nRequest: {query}\n\nContent goes here..."
            
            with open(filepath, 'w') as f:
                f.write(content)
            
            return f"File created: {filepath}"
        except Exception as e:
            return f"File creation failed: {e}"
    
    def run(self):
        """Simple conversation loop"""
        print("BOWEN ready")
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ["quit", "exit", "bye"]:
                    print("Bye")
                    break
                
                response = self.process(user_input)
                print(f"\nBOWEN: {response}")
                
            except (EOFError, KeyboardInterrupt):
                print("\nBye")
                break
            except Exception as e:
                print(f"\nError: {e}")

def main():
    try:
        bowen = BOWEN()
        bowen.run()
    except Exception as e:
        print(f"Failed to start BOWEN: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()