#!/usr/bin/env python3
"""
BOWEN Complete System Architecture Analysis
Shows: Git status, storage locations, all engines, connections
"""

import os
import json
import subprocess
from pathlib import Path

class SystemAnalyzer:
    def __init__(self):
        self.bowen_path = Path('/Users/yimi/Desktop/bowen')
        
    def check_git_status(self):
        """Check Git configuration and remote"""
        print("\n" + "="*60)
        print("📦 GIT & BACKUP STATUS")
        print("="*60 + "\n")
        
        os.chdir(self.bowen_path)
        
        # Check if git is initialized
        if not (self.bowen_path / '.git').exists():
            print("❌ Git NOT initialized")
            print("   Run: cd /Users/yimi/Desktop/bowen && git init")
            return
        
        print("✅ Git initialized\n")
        
        # Check remote
        try:
            result = subprocess.run(['git', 'remote', '-v'], 
                                  capture_output=True, text=True)
            if result.stdout:
                print("📡 Remote repositories:")
                print(result.stdout)
            else:
                print("⚠️  No remote repository configured")
                print("   To add GitHub: gh repo create bowen-memory --private")
        except:
            print("⚠️  Could not check remotes")
        
        # Check last commit
        try:
            result = subprocess.run(['git', 'log', '-1', '--oneline'], 
                                  capture_output=True, text=True)
            if result.stdout:
                print(f"\n📝 Last commit: {result.stdout.strip()}")
        except:
            print("\n⚠️  No commits yet")
        
        # Check what's tracked
        try:
            result = subprocess.run(['git', 'status', '--short'], 
                                  capture_output=True, text=True)
            if result.stdout:
                print(f"\n📊 Git status:")
                print(result.stdout)
            else:
                print("\n✅ Working tree clean")
        except:
            pass
    
    def map_storage_locations(self):
        """Map all data storage locations"""
        print("\n" + "="*60)
        print("💾 DATA STORAGE LOCATIONS")
        print("="*60 + "\n")
        
        storage_map = {
            "Memory (Facts & Deadlines)": "memory.json",
            "User Context": "user_context.yaml",
            "Knowledge Base": "knowledge/concepts.json",
            "Concept Connections": "knowledge/connections.json",
            "Conversation History": "conversations/",
            "Research Outputs": "bowen_outputs/research/",
            "Generated Files": "bowen_outputs/"
        }
        
        for name, path in storage_map.items():
            full_path = self.bowen_path / path
            if full_path.exists():
                if full_path.is_file():
                    size = full_path.stat().st_size
                    print(f"✅ {name}")
                    print(f"   Location: {full_path}")
                    print(f"   Size: {size:,} bytes\n")
                else:
                    try:
                        files = list(full_path.iterdir())
                        print(f"✅ {name}")
                        print(f"   Location: {full_path}")
                        print(f"   Contains: {len(files)} items\n")
                    except:
                        print(f"⚠️  {name}: {full_path} (empty)\n")
            else:
                print(f"❌ {name}: NOT FOUND")
                print(f"   Expected at: {full_path}\n")
    
    def list_all_engines(self):
        """List all engines and their purposes"""
        print("\n" + "="*60)
        print("⚙️  ALL ENGINES")
        print("="*60 + "\n")
        
        engines = {
            "CORE INTELLIGENCE": {
                "bowen_core.py": "Main orchestration, Claude API integration",
                "cli.py": "Conversational interface, intent detection",
                "config.py": "Configuration, API keys, settings"
            },
            "LEARNING & MEMORY": {
                "engines/autonomous_learner.py": "Self-teaching, concept research",
                "engines/adaptive_memory.py": "Context-aware memory management",
                "engines/concept_detector.py": "Unknown concept detection" if (self.bowen_path / "engines/concept_detector.py").exists() else None
            },
            "ACADEMIC": {
                "engines/syllabus_parser.py": "Extract deadlines from PDFs",
                "engines/manual_academic.py": "Quick deadline input",
                "engines/outlook_connector.py": "CMU email/calendar sync"
            },
            "CODE & DEVELOPMENT": {
                "engines/code_agent.py": "Code generation, project creation",
                "engines/computer_tools.py": "File operations, system commands",
                "engines/vision_engine.py": "Screen capture, image analysis"
            },
            "RESEARCH & DOCUMENTS": {
                "engines/research_engine.py": "Web research, codebase analysis",
                "engines/document_engine.py": "PDF/DOCX/HTML creation",
                "engines/advanced_documents.py": "Essays, presentations" if (self.bowen_path / "engines/advanced_documents.py").exists() else None
            },
            "WORKFLOW & AUTOMATION": {
                "engines/workflow_orchestrator.py": "Multi-step task execution",
                "engines/proactive_assistant.py": "Proactive intelligence",
                "engines/backup_manager.py": "Git auto-backup"
            },
            "SYSTEM": {
                "engines/self_upgrader.py": "Model upgrade detection/execution"
            }
        }
        
        for category, engine_dict in engines.items():
            print(f"\n{category}:")
            for engine, description in engine_dict.items():
                if description is None:
                    continue
                path = self.bowen_path / engine
                status = "✅" if path.exists() else "❌"
                print(f"{status} {engine}")
                print(f"   → {description}")
    
    def map_engine_connections(self):
        """Show how engines connect to each other"""
        print("\n" + "="*60)
        print("🔗 ENGINE CONNECTIONS")
        print("="*60 + "\n")
        
        print("DATA FLOW:\n")
        
        print("1️⃣  USER INPUT")
        print("   ↓")
        print("   cli.py (Intent Detection)")
        print("   ↓")
        print("   ├─→ Manual deadline? → manual_academic.py → memory.json")
        print("   ├─→ PDF upload? → syllabus_parser.py → memory.json")
        print("   ├─→ Unknown concept? → autonomous_learner.py → knowledge/")
        print("   ├─→ Code request? → code_agent.py → file creation")
        print("   ├─→ Research? → research_engine.py → web search")
        print("   └─→ General chat? → bowen_core.py → Claude API")
        
        print("\n2️⃣  MEMORY SYSTEM")
        print("   memory.json ←→ All engines read/write")
        print("   ├─→ Facts: Deadlines, user info")
        print("   ├─→ Courses: Academic data")
        print("   └─→ Conversations: Chat history")
        
        print("\n3️⃣  KNOWLEDGE SYSTEM")
        print("   autonomous_learner.py")
        print("   ├─→ research_engine.py (web search)")
        print("   ├─→ knowledge/concepts.json (save)")
        print("   └─→ bowen_core.py (Claude for analysis)")
        
        print("\n4️⃣  ACADEMIC WORKFLOW")
        print("   syllabus_parser.py → memory.json")
        print("   manual_academic.py → memory.json")
        print("   outlook_connector.py → calendar/email sync")
        print("   backup_manager.py → Git commit → GitHub")
        
        print("\n5️⃣  CODE WORKFLOW")
        print("   code_agent.py")
        print("   ├─→ computer_tools.py (file ops)")
        print("   ├─→ vision_engine.py (screen capture)")
        print("   └─→ bowen_core.py (Claude for generation)")
        
        print("\n6️⃣  BACKUP FLOW")
        print("   [Any data change]")
        print("   ↓")
        print("   backup_manager.py")
        print("   ↓")
        print("   Git commit")
        print("   ↓")
        print("   GitHub remote (if configured)")
    
    def show_critical_dependencies(self):
        """Show what depends on what"""
        print("\n" + "="*60)
        print("📊 CRITICAL DEPENDENCIES")
        print("="*60 + "\n")
        
        print("EVERYTHING depends on:")
        print("  • config.py → Claude API key")
        print("  • bowen_core.py → Claude API client")
        print("  • memory.json → All facts/deadlines\n")
        
        print("Academic features depend on:")
        print("  • syllabus_parser.py → PyMuPDF, dateparser")
        print("  • manual_academic.py → dateparser")
        print("  • outlook_connector.py → msal (Microsoft Graph)\n")
        
        print("Learning depends on:")
        print("  • autonomous_learner.py → research_engine.py")
        print("  • research_engine.py → web search capabilities")
        print("  • knowledge/concepts.json → Persistent storage\n")
        
        print("Backup depends on:")
        print("  • Git installed")
        print("  • GitHub CLI (gh) for remote sync")
        print("  • Write permissions on /Users/yimi/Desktop/bowen")
    
    def verify_connections(self):
        """Test that engines can actually talk to each other"""
        print("\n" + "="*60)
        print("🔍 CONNECTION VERIFICATION")
        print("="*60 + "\n")
        
        import sys
        sys.path.insert(0, str(self.bowen_path))
        
        tests = [
            ("CLI → Memory", "from cli import ConversationalInterface; cli = ConversationalInterface()"),
            ("CLI → Academic", "from engines.manual_academic import ManualAcademic; m = ManualAcademic()"),
            ("CLI → Backup", "from engines.backup_manager import BackupManager; b = BackupManager()"),
            ("Academic → Memory", "import json; m = json.load(open('memory.json'))"),
            ("Learning → Knowledge", "import json; k = json.load(open('knowledge/concepts.json'))")
        ]
        
        for name, test_code in tests:
            try:
                exec(test_code)
                print(f"✅ {name}: CONNECTED")
            except Exception as e:
                print(f"❌ {name}: FAILED")
                print(f"   Error: {str(e)[:80]}")
    
    def generate_visual_map(self):
        """Create a simple ASCII visual map"""
        print("\n" + "="*60)
        print("🗺️  BOWEN SYSTEM MAP")
        print("="*60 + "\n")
        
        print("""
┌─────────────────────────────────────────────────────────┐
│                        USER                             │
│                          ↓                              │
│                       cli.py                            │
│              (Intent Detection & Routing)               │
└────────────┬────────────────────────────┬───────────────┘
             │                            │
      ┌──────┴──────┐            ┌────────┴────────┐
      │   MEMORY    │            │   CLAUDE API    │
      │ memory.json │            │  bowen_core.py  │
      └──────┬──────┘            └────────┬────────┘
             │                            │
   ┌─────────┼────────────────────────────┼──────────┐
   │         │                            │          │
┌──┴──┐  ┌──┴──┐  ┌──────────┐  ┌────────┴────┐  ┌─┴────┐
│LEARN│  │ACAD │  │   CODE   │  │  RESEARCH   │  │BACKUP│
│     │  │     │  │          │  │             │  │      │
│auto │  │sylla│  │code_     │  │research_    │  │backup│
│_lear│  │bus_ │  │agent.py  │  │engine.py    │  │_mgr  │
│ner  │  │parse│  │          │  │             │  │.py   │
└──┬──┘  └──┬──┘  └────┬─────┘  └──────┬──────┘  └──┬───┘
   │        │          │               │            │
   ↓        ↓          ↓               ↓            ↓
knowledge/ memory.json files/      web/APIs      GitHub
concepts.json courses/  code/      results/      remote
        """)
        
        print("\nKEY:")
        print("  • MEMORY: Central data store (memory.json)")
        print("  • LEARN: Autonomous concept learning")
        print("  • ACAD: Academic assistant (deadlines, syllabi)")
        print("  • CODE: Code generation and file operations")
        print("  • RESEARCH: Web research and analysis")
        print("  • BACKUP: Git version control")

def main():
    print("\n" + "="*60)
    print("🔍 BOWEN COMPLETE SYSTEM ANALYSIS")
    print("="*60)
    
    analyzer = SystemAnalyzer()
    
    analyzer.check_git_status()
    analyzer.map_storage_locations()
    analyzer.list_all_engines()
    analyzer.map_engine_connections()
    analyzer.show_critical_dependencies()
    analyzer.verify_connections()
    analyzer.generate_visual_map()
    
    print("\n" + "="*60)
    print("✅ ANALYSIS COMPLETE")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()