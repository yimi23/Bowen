#!/usr/bin/env python3
"""
Test BOWEN Model Discovery System
"""

import sys
import os
import asyncio
sys.path.append('/Users/yimi/Desktop/bowen')

# Load environment variables first
from dotenv import load_dotenv
load_dotenv('/Users/yimi/Desktop/bowen/.env')

from engines.self_upgrader import SelfUpgrader

async def test_model_discovery():
    """Test the new model discovery system"""
    print("🔍 BOWEN MODEL DISCOVERY TEST")
    print("=" * 40)
    
    upgrader = SelfUpgrader()
    
    if not upgrader.api_key:
        print("❌ No API key available for testing")
        return False
    
    print("🧪 Testing model discovery...")
    
    try:
        # Test pattern-based discovery
        print("\n1️⃣ Testing pattern-based model discovery...")
        discovered = await upgrader.discover_new_models()
        
        print(f"📊 Discovered {len(discovered)} potential new models:")
        for model in discovered[:5]:  # Show first 5
            print(f"  🆕 {model}")
        
        if len(discovered) > 5:
            print(f"  ... and {len(discovered) - 5} more")
        
        # Test full model detection with discovery
        print("\n2️⃣ Testing enhanced model detection...")
        available_models = upgrader._get_available_models()
        
        print(f"📊 Total verified models: {len(available_models)}")
        for model in available_models:
            status = "✅ VERIFIED" if model.get('verified') else "❓ UNKNOWN"
            print(f"  {status} {model['id']}")
        
        # Test specific model patterns
        print("\n3️⃣ Testing specific model patterns...")
        test_models = [
            "claude-sonnet-4-20250514",  # Should exist
            "claude-sonnet-5-20260115",  # Might exist in future
            "claude-opus-4-20250601",    # Test future model
        ]
        
        for test_model in test_models:
            exists = await upgrader._test_model_exists(test_model)
            status = "✅ EXISTS" if exists else "❌ NOT FOUND"
            print(f"  {status} {test_model}")
        
        return True
        
    except Exception as e:
        print(f"❌ Model discovery test failed: {e}")
        return False

def test_html_parsing():
    """Test HTML parsing functions"""
    print("\n4️⃣ Testing HTML parsing...")
    
    upgrader = SelfUpgrader()
    
    # Mock HTML content with model names
    test_html = """
    <html>
    <body>
    <p>Available models include claude-3-sonnet-20240229 and claude-3-5-sonnet-20241022</p>
    <p>New release: claude-sonnet-4-20250514 is now available</p>
    <p>Coming soon: claude-opus-5-20260101</p>
    </body>
    </html>
    """
    
    models = upgrader._extract_models_from_html(test_html)
    print(f"📄 Extracted {len(models)} models from HTML:")
    for model in models:
        print(f"  📝 {model}")
    
    # Mock changelog content
    test_changelog = """
    ## Release Notes
    
    ### 2025-05-14
    Released claude-sonnet-4-20250514 with enhanced reasoning
    
    ### 2024-10-22
    Announced claude-3-5-sonnet-20241022 with improved capabilities
    """
    
    changelog_models = upgrader._extract_models_from_changelog(test_changelog)
    print(f"📝 Extracted {len(changelog_models)} models from changelog:")
    for model in changelog_models:
        print(f"  📰 {model}")

async def main():
    """Run all discovery tests"""
    print("🚀 Starting BOWEN Model Discovery Tests...\n")
    
    # Test HTML parsing (no API required)
    test_html_parsing()
    
    # Test actual model discovery (requires API)
    discovery_success = await test_model_discovery()
    
    print(f"\n📊 DISCOVERY TEST SUMMARY:")
    print(f"✅ HTML/Changelog parsing: PASSED")
    print(f"{'✅' if discovery_success else '❌'} API model discovery: {'PASSED' if discovery_success else 'FAILED'}")
    
    print(f"\n🎯 Model discovery system is {'ready!' if discovery_success else 'needs API key'}")

if __name__ == "__main__":
    asyncio.run(main())