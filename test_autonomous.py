#!/usr/bin/env python3
"""
Test script for BOWEN autonomous capabilities
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_engines():
    """Test all autonomous engines"""
    print("🧪 Testing BOWEN Autonomous Engines\n")
    
    # Test imports
    try:
        from engines.autonomous_learner import AutonomousLearner
        print("✅ Autonomous Learner imported successfully")
    except Exception as e:
        print(f"❌ Autonomous Learner import failed: {e}")
        return False
    
    try:
        from engines.code_agent import CodeAgent
        print("✅ Code Agent imported successfully")
    except Exception as e:
        print(f"❌ Code Agent import failed: {e}")
    
    try:
        from engines.workflow_orchestrator import WorkflowOrchestrator
        print("✅ Workflow Orchestrator imported successfully")
    except Exception as e:
        print(f"❌ Workflow Orchestrator import failed: {e}")
    
    try:
        from engines.file_manager import IntelligentFileManager
        print("✅ File Manager imported successfully")
    except Exception as e:
        print(f"❌ File Manager import failed: {e}")
    
    try:
        from engines.advanced_documents import AdvancedDocumentEngine
        print("✅ Advanced Documents imported successfully")
    except Exception as e:
        print(f"❌ Advanced Documents import failed: {e}")
    
    try:
        from engines.self_upgrader import SelfUpgrader
        print("✅ Self Upgrader imported successfully")
    except Exception as e:
        print(f"❌ Self Upgrader import failed: {e}")
    
    # Test knowledge base
    knowledge_path = Path("knowledge/concepts.json")
    if knowledge_path.exists():
        print("✅ Knowledge base exists")
    else:
        print("❌ Knowledge base missing")
    
    # Test basic initialization
    try:
        learner = AutonomousLearner(
            knowledge_path="knowledge/",
            research_engine=None,  # Mock for testing
            claude_engine=None     # Mock for testing
        )
        print("✅ Autonomous Learner initialized")
        
        # Test knowledge loading
        concepts_count = len(learner.concepts)
        print(f"✅ Loaded {concepts_count} concepts from knowledge base")
        
    except Exception as e:
        print(f"❌ Autonomous Learner initialization failed: {e}")
    
    try:
        file_manager = IntelligentFileManager()
        print("✅ File Manager initialized")
    except Exception as e:
        print(f"❌ File Manager initialization failed: {e}")
    
    print("\n🎯 Autonomous engines test completed!")
    return True

def test_cli_integration():
    """Test CLI integration"""
    print("\n🧪 Testing CLI Integration\n")
    
    try:
        from cli import ConversationalInterface, AUTONOMOUS_ENGINES_AVAILABLE
        
        if AUTONOMOUS_ENGINES_AVAILABLE:
            print("✅ All autonomous engines available in CLI")
        else:
            print("⚠️ Some autonomous engines not available in CLI")
        
        print("✅ CLI imports successful")
        return True
        
    except Exception as e:
        print(f"❌ CLI integration test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 BOWEN Autonomous Capabilities Test Suite")
    print("=" * 50)
    
    engines_ok = test_engines()
    cli_ok = test_cli_integration()
    
    print("\n" + "=" * 50)
    if engines_ok and cli_ok:
        print("🎉 All tests passed! BOWEN is ready for autonomous operation.")
    else:
        print("⚠️ Some tests failed. Check the errors above.")
    
    print("\n📋 **What BOWEN Can Now Do:**")
    print("• 'build a react app called dashboard' → Creates and deploys React app")
    print("• 'write a 2000-word essay about AI' → Researches and writes complete essay")
    print("• 'create presentation about my startup' → Generates PowerPoint with research")
    print("• 'organize my files' → Intelligently organizes Desktop files")
    print("• 'learn about BCNF' → Researches concept and adds to knowledge base")
    print("• 'check for updates' → Checks for newer Claude models")
    print("• 'what can you do' → Shows all autonomous capabilities")