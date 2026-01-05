#!/usr/bin/env python3
"""
BOWEN Framework API Key Configuration Helper
Helps users securely add their Anthropic API key to the .env file
"""

import os
import sys
from pathlib import Path

def main():
    print("🔑 BOWEN Framework - API Key Configuration")
    print("=" * 50)
    
    # Check if .env exists
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env file not found!")
        print("Run 'python setup.py' first to create the configuration file.")
        sys.exit(1)
    
    # Read current .env content
    env_content = env_file.read_text()
    
    # Check if API key is already set
    if 'ANTHROPIC_API_KEY=' in env_content and not env_content.count('ANTHROPIC_API_KEY=\n'):
        current_key = None
        for line in env_content.split('\n'):
            if line.startswith('ANTHROPIC_API_KEY=') and '=' in line:
                current_key = line.split('=', 1)[1]
                break
        
        if current_key:
            masked_key = current_key[:7] + '*' * (len(current_key) - 11) + current_key[-4:] if len(current_key) > 11 else '*' * len(current_key)
            print(f"✅ API key already configured: {masked_key}")
            
            response = input("Do you want to update it? (y/N): ")
            if response.lower() != 'y':
                print("✅ Keeping existing API key")
                sys.exit(0)
    
    # Instructions
    print("\n📝 To get your Anthropic API key:")
    print("1. Go to: https://console.anthropic.com/settings/keys")
    print("2. Click 'Create Key'")
    print("3. Copy the key (it starts with 'sk-ant-')")
    print("4. Paste it below")
    
    # Get API key from user
    print("\n🔐 Enter your API key:")
    api_key = input("ANTHROPIC_API_KEY: ").strip()
    
    if not api_key:
        print("❌ No API key provided")
        sys.exit(1)
    
    # Validate format
    if not api_key.startswith('sk-ant-'):
        print("⚠️  Warning: API key doesn't start with 'sk-ant-'")
        print("Are you sure this is correct?")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("❌ Aborted")
            sys.exit(1)
    
    # Update .env file
    lines = env_content.split('\n')
    updated_lines = []
    key_found = False
    
    for line in lines:
        if line.startswith('ANTHROPIC_API_KEY='):
            updated_lines.append(f'ANTHROPIC_API_KEY={api_key}')
            key_found = True
        else:
            updated_lines.append(line)
    
    if not key_found:
        # Add the key if the line doesn't exist
        updated_lines.append(f'ANTHROPIC_API_KEY={api_key}')
    
    # Write back to .env
    env_file.write_text('\n'.join(updated_lines))
    
    print("✅ API key successfully added to .env file")
    
    # Test the configuration
    print("\n🧪 Testing configuration...")
    try:
        sys.path.append('.')
        from config import get_config
        
        config = get_config()
        if config.has_anthropic_key:
            print("✅ API key validation successful!")
            print("🎉 BOWEN Framework is ready to use!")
            print("\nNext steps:")
            print("  python cli.py")
        else:
            print("❌ API key validation failed")
            print("Please check the key format and try again")
    except ImportError:
        print("⚠️  Could not test configuration (missing dependencies)")
        print("Run 'pip install -r requirements.txt' first")
    except Exception as e:
        print(f"⚠️  Configuration test error: {e}")

if __name__ == "__main__":
    main()