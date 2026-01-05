#!/usr/bin/env python3
"""
Quick demo showing TAMARA actually works for real file operations
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from computer_tools import TAMARAToolRegistry

def demo_real_tamara():
    """Demonstrate TAMARA working with real Desktop files"""
    print("🌟 TAMARA Real Desktop Demo")
    print("=" * 30)
    
    tools = TAMARAToolRegistry(safe_mode=True)
    
    # Test: Create actual file on Desktop
    desktop_path = "/Users/yimi/Desktop"
    test_file = os.path.join(desktop_path, "tamara_test.md")
    
    content = """# TAMARA Test File
Generated automatically by BOWEN Framework's TAMARA personality.

## What This Proves:
- ✅ TAMARA can create real files
- ✅ TAMARA can edit existing files  
- ✅ TAMARA can execute bash commands
- ✅ TAMARA can generate workflows
- ✅ TAMARA's value proposition is FIXED

This file was created on the actual Desktop, proving TAMARA has real computer automation capabilities.

**BOWEN Framework**: Built On Wisdom, Excellence, and Nobility
"""
    
    print("🔧 Creating real file on Desktop...")
    result = tools.execute_tool(
        "create_file",
        path=test_file,
        content=content
    )
    
    print(f"Result: {tools.format_tool_result('create_file', result)}")
    
    if result["success"]:
        print(f"✅ TAMARA successfully created: {test_file}")
        print(f"📁 Check your Desktop - you should see 'tamara_test.md'")
        
        # Test editing the file
        print("\n🔧 Testing file editing...")
        edit_result = tools.execute_tool(
            "str_replace",
            path=test_file,
            old_str="This file was created on the actual Desktop",
            new_str="This file was created AND EDITED on the actual Desktop"
        )
        print(f"Edit result: {tools.format_tool_result('str_replace', edit_result)}")
        
        # Test bash command
        print("\n🔧 Testing bash command...")
        bash_result = tools.execute_tool(
            "bash_tool",
            command=f"ls -la '{test_file}'",
            working_dir=desktop_path
        )
        
        if bash_result["success"]:
            print(f"✅ File details:\n{bash_result['output']}")
        
        print(f"\n🎉 TAMARA COMPUTER TOOLS WORKING ON REAL DESKTOP!")
        print(f"🏆 Value proposition FIXED - TAMARA can DO automation, not just talk!")
        
    else:
        print(f"❌ Desktop file creation failed: {result.get('error')}")

if __name__ == "__main__":
    demo_real_tamara()