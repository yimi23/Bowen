#!/usr/bin/env python3
"""
BOWEN Framework Demo: Real AI vs Template Responses
Shows the critical difference between actual Claude integration and templates
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bowen_core import BOWENFramework

def demo_without_api():
    """Demo without API key - shows what happens without real AI"""
    print("🚫 DEMO: BOWEN Without API Key (Template Responses)")
    print("=" * 60)
    
    # Ensure no API key is set
    if 'ANTHROPIC_API_KEY' in os.environ:
        del os.environ['ANTHROPIC_API_KEY']
    
    bowen = BOWENFramework()
    
    print(f"🤖 AI Status: {'✅ ENABLED' if bowen.is_ai_enabled() else '❌ DISABLED'}")
    
    test_input = "Should I build Remi Guardian or FraudZero first?"
    print(f"\nInput: {test_input}")
    
    response = bowen.process_input(test_input)
    print(f"\n❌ WITHOUT API - Response:\n{response}")
    print("\n" + "="*60)

def demo_with_api():
    """Demo with API key - shows real Claude responses"""
    print("\n✅ DEMO: BOWEN With Real Claude API")
    print("=" * 60)
    
    # Check if user has API key
    api_key = input("Enter your ANTHROPIC_API_KEY (or 'skip' to skip): ").strip()
    
    if api_key.lower() == 'skip':
        print("Skipping real AI demo - API key not provided")
        return
    
    if not api_key.startswith('sk-ant-'):
        print("❌ Invalid API key format. Should start with 'sk-ant-'")
        return
    
    # Set API key
    os.environ['ANTHROPIC_API_KEY'] = api_key
    
    # Reinitialize BOWEN with API key
    bowen = BOWENFramework()
    
    print(f"🤖 AI Status: {'✅ ENABLED' if bowen.is_ai_enabled() else '❌ DISABLED'}")
    
    if not bowen.is_ai_enabled():
        print("❌ API key invalid or network error")
        return
    
    test_input = "Should I build Remi Guardian or FraudZero first? Consider strategic priorities."
    print(f"\nInput: {test_input}")
    print("🔄 Calling real Claude API...")
    
    try:
        response = bowen.process_input(test_input)
        print(f"\n✅ WITH REAL AI - CAPTAIN's Response:\n{response}")
        
        # Test personality switch
        print(f"\n🔄 Switching to TAMARA...")
        from bowen_core import PersonalityType
        switch_response = bowen.switch_personality(PersonalityType.TAMARA)
        print(f"{switch_response}")
        
        # Same question with TAMARA
        response2 = bowen.process_input(test_input)
        print(f"\n✅ WITH REAL AI - TAMARA's Response:\n{response2}")
        
    except Exception as e:
        print(f"❌ API Error: {e}")

def show_critical_differences():
    """Show the critical differences between real AI and templates"""
    print("\n🔍 CRITICAL DIFFERENCES: Real AI vs Templates")
    print("=" * 60)
    
    differences = [
        ("Response Quality", "Unique, contextual analysis", "Generic template responses"),
        ("Reasoning", "Actual Claude Sonnet 4 intelligence", "Static pattern matching"),
        ("Personality", "Dynamic character adaptation", "Fixed phrase replacement"),
        ("Memory", "Context-aware conversations", "Basic pattern storage"),
        ("Value", "$29/month justified", "Worthless template system"),
        ("User Experience", "Professional AI assistant", "Broken demo"),
        ("Business Model", "Viable SaaS product", "Complete failure")
    ]
    
    print(f"{'Aspect':<20} {'WITH API KEY':<30} {'WITHOUT API KEY':<30}")
    print("-" * 80)
    
    for aspect, with_api, without_api in differences:
        print(f"{aspect:<20} ✅ {with_api:<28} ❌ {without_api:<28}")

if __name__ == "__main__":
    print("🧭 BOWEN Framework - Real AI Integration Demo")
    print("Built On Wisdom, Excellence, and Nobility")
    print("=" * 70)
    
    # Show what happens without API
    demo_without_api()
    
    # Show critical differences
    show_critical_differences()
    
    # Offer real API demo
    demo_with_api()
    
    print(f"\n🏆 CONCLUSION:")
    print(f"   Without ANTHROPIC_API_KEY: Worthless template system")
    print(f"   With ANTHROPIC_API_KEY: Professional AI assistant worth $29/month")
    print(f"   Get your key: https://console.anthropic.com/settings/keys")
    print("=" * 70)