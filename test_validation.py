#!/usr/bin/env python3
"""
Test BOWEN Anti-Hallucination Validation Systems
"""

import sys
import os
sys.path.append('/Users/yimi/Desktop/bowen')

# Load environment variables first
from dotenv import load_dotenv
load_dotenv('/Users/yimi/Desktop/bowen/.env')

from engines.code_agent import CodeAgent
from engines.self_upgrader import SelfUpgrader
from engines.autonomous_learner import AutonomousLearner

def test_code_validation():
    """Test TypeScript code validation to prevent hallucinated APIs"""
    print("🧪 Testing Code Agent validation...")
    
    code_agent = CodeAgent()
    
    # Test 1: Valid React code
    valid_code = '''
import React, { useState } from 'react';

const TestComponent: React.FC = () => {
  const [count, setCount] = useState(0);
  
  return (
    <div>
      <button onClick={() => setCount(count + 1)}>
        Count: {count}
      </button>
    </div>
  );
};

export default TestComponent;
'''
    
    result1 = code_agent._validate_typescript_code(valid_code, "TestComponent")
    print(f"✅ Valid code test: {result1}")
    
    # Test 2: Hallucinated React hooks (should fail)
    invalid_code = '''
import React, { useState, useAutoState, useMagic } from 'react';

const BadComponent: React.FC = () => {
  const [count, setCount] = useState(0);
  const autoData = useAutoState();  // HALLUCINATED
  const magic = useMagic('perfect');  // HALLUCINATED
  
  return <div>Bad component</div>;
};

export default BadComponent;
'''
    
    result2 = code_agent._validate_typescript_code(invalid_code, "BadComponent")
    print(f"❌ Invalid code test: {result2}")
    
    # Test 3: Suspicious imports (should fail)
    suspicious_code = '''
import React from 'react-super';  // HALLUCINATED PACKAGE
import { usePerfect } from 'react-enhanced';  // HALLUCINATED

const SuspiciousComponent = () => {
  return <div>Suspicious</div>;
};

export default SuspiciousComponent;
'''
    
    result3 = code_agent._validate_typescript_code(suspicious_code, "SuspiciousComponent")
    print(f"🚨 Suspicious code test: {result3}")
    
    return all([
        result1['valid'] == True,
        result2['valid'] == False,
        result3['valid'] == False
    ])

def test_python_validation():
    """Test Python code validation"""
    print("\n🧪 Testing Python code validation...")
    
    code_agent = CodeAgent()
    
    # Test 1: Valid Python code
    valid_python = '''
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World"}

if __name__ == "__main__":
    uvicorn.run(app)
'''
    
    result1 = code_agent._validate_python_code(valid_python)
    print(f"✅ Valid Python test: {result1}")
    
    # Test 2: Hallucinated packages (should fail)
    invalid_python = '''
from super_fastapi import MagicAPI  # HALLUCINATED
from enhanced_fastapi import PerfectFramework  # HALLUCINATED

app = MagicAPI()

@app.magic_route("/")
def perfect_endpoint():
    return PerfectFramework.auto_response()
'''
    
    result2 = code_agent._validate_python_code(invalid_python)
    print(f"❌ Invalid Python test: {result2}")
    
    return result1['valid'] == True and result2['valid'] == False

def test_model_detection():
    """Test Self-Upgrader model detection (should use real API testing)"""
    print("\n🧪 Testing Self-Upgrader model detection...")
    
    # Test the anti-hallucination approach without API key
    upgrader = SelfUpgrader()
    
    # Check that it returns fallback safely when no API key
    if not upgrader.api_key:
        print("⚠️  No API key - testing fallback behavior")
        # Check known_models structure has real Anthropic model names
        known_models = upgrader.known_models
        real_models = [
            "claude-3-haiku-20240307",
            "claude-3-5-sonnet-20241022", 
            "claude-sonnet-4-20250514"
        ]
        
        has_real_models = any(model in known_models for model in real_models)
        print(f"📝 Known models include real Anthropic models: {has_real_models}")
        
        # Check date extraction works
        test_date = upgrader._extract_date_from_model_name("claude-3-5-sonnet-20241022")
        correct_date = test_date == "2024-10-22"
        print(f"🗓️  Date extraction works: {correct_date}")
        
        return has_real_models and correct_date
    else:
        # Test with real API
        available_models = upgrader._get_available_models()
        all_verified = all(model.get('verified', False) for model in available_models)
        return len(available_models) > 0 and all_verified

def test_research_verification():
    """Test Autonomous Learner research verification"""
    print("\n🧪 Testing Autonomous Learner research verification...")
    
    # Mock research engine for testing
    class MockResearchEngine:
        def research_and_report(self, query):
            return f"Research results for: {query}\nReal information from verified sources with detailed explanations and examples."
    
    # Mock Claude engine for testing  
    class MockClaudeEngine:
        def __init__(self):
            self.model = "test-model"
            
        @property 
        def client(self):
            return MockClient()
    
    class MockClient:
        @property
        def messages(self):
            return MockMessages()
            
    class MockMessages:
        def create(self, **kwargs):
            # Mock response with proper structure
            class MockResponse:
                def __init__(self):
                    self.content = [MockContent()]
                    
            class MockContent:
                def __init__(self):
                    self.text = '''{"concept": "test_concept", "definition": "Research-based definition", "category": "programming", "confidence": 0.8, "sources": ["test_source"], "user_relevance": "high"}'''
            
            return MockResponse()
    
    research_engine = MockResearchEngine()
    claude_engine = MockClaudeEngine()
    
    learner = AutonomousLearner("/tmp/test_knowledge", research_engine, claude_engine)
    
    # Test concept research with validation  
    result = learner.research_concept("test_concept")
    
    print(f"📊 Research result keys: {list(result.keys())}")
    
    # Verify it includes verification requirements
    has_confidence = 'confidence' in result
    has_sources = 'sources' in result
    has_learned_at = 'learned_at' in result
    has_research_validation = len(result.get('sources', [])) > 0
    
    print(f"🔍 Includes confidence scoring: {has_confidence}")
    print(f"📚 Includes source attribution: {has_sources}")
    print(f"📅 Includes timestamp: {has_learned_at}")
    print(f"🔬 Has research validation: {has_research_validation}")
    
    return has_confidence and has_sources and has_learned_at

def main():
    """Run all validation tests"""
    print("🛡️ BOWEN ANTI-HALLUCINATION VALIDATION TESTS")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 4
    
    # Test code validation
    if test_code_validation():
        print("✅ Code validation: PASSED")
        tests_passed += 1
    else:
        print("❌ Code validation: FAILED")
    
    # Test Python validation
    if test_python_validation():
        print("✅ Python validation: PASSED")
        tests_passed += 1
    else:
        print("❌ Python validation: FAILED")
    
    # Test model detection
    if test_model_detection():
        print("✅ Model detection: PASSED")
        tests_passed += 1
    else:
        print("❌ Model detection: FAILED")
    
    # Test research verification
    if test_research_verification():
        print("✅ Research verification: PASSED")  
        tests_passed += 1
    else:
        print("❌ Research verification: FAILED")
    
    print(f"\n📊 VALIDATION SUMMARY: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 ALL ANTI-HALLUCINATION VALIDATIONS PASSED!")
        return True
    else:
        print("⚠️  Some validations failed - review anti-hallucination protocols")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)