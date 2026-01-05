#!/usr/bin/env python3
"""
BOWEN Framework Setup Script
Proper environment configuration and validation
"""

import os
import sys
import shutil
from pathlib import Path

def create_env_file():
    """Create .env file from .env.example"""
    env_example = Path('.env.example')
    env_file = Path('.env')
    
    if not env_example.exists():
        print("❌ .env.example not found")
        return False
    
    if env_file.exists():
        response = input("⚠️  .env file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("✅ Keeping existing .env file")
            return True
    
    shutil.copy('.env.example', '.env')
    print("✅ Created .env file from template")
    return True

def setup_api_key():
    """Help user set up API key"""
    print("\n🔑 API Key Configuration")
    print("=" * 30)
    
    print("1. Go to: https://console.anthropic.com/settings/keys")
    print("2. Create a new API key")
    print("3. Copy the key (starts with 'sk-ant-')")
    
    api_key = input("\nPaste your Anthropic API key: ").strip()
    
    if not api_key:
        print("⚠️  No API key provided - AI features will be disabled")
        return False
    
    if not api_key.startswith('sk-ant-'):
        print("⚠️  API key format looks incorrect (should start with 'sk-ant-')")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False
    
    # Update .env file
    env_file = Path('.env')
    if env_file.exists():
        content = env_file.read_text()
        content = content.replace(
            'ANTHROPIC_API_KEY=sk-ant-your-actual-key-here',
            f'ANTHROPIC_API_KEY={api_key}'
        )
        env_file.write_text(content)
        print("✅ API key added to .env file")
        return True
    else:
        print("❌ .env file not found")
        return False

def setup_directories():
    """Create necessary directories"""
    print("\n📁 Directory Setup")
    print("=" * 20)
    
    directories = [
        'bowen_outputs',
        'logs',
        'cache'
    ]
    
    for directory in directories:
        path = Path(directory)
        path.mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")

def install_dependencies():
    """Install Python dependencies"""
    print("\n📦 Installing Dependencies")
    print("=" * 30)
    
    try:
        import subprocess
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ All dependencies installed successfully")
            return True
        else:
            print(f"❌ Failed to install dependencies: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def test_configuration():
    """Test the configuration"""
    print("\n🧪 Testing Configuration")
    print("=" * 25)
    
    try:
        # Import and test configuration
        sys.path.append('.')
        from config import get_config
        
        config = get_config()
        
        print(f"API Key: {'✅ Configured' if config.has_anthropic_key else '❌ Missing'}")
        print(f"Output Dir: ✅ {config.output_directory}")
        print(f"Safe Mode: ✅ {config.tamara_safe_mode}")
        
        if config.has_anthropic_key:
            print("🎉 Configuration looks good!")
            return True
        else:
            print("⚠️  AI features will be disabled without API key")
            return False
            
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Main setup process"""
    print("🧭 BOWEN Framework Setup")
    print("Built On Wisdom, Excellence, and Nobility")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path('bowen_core.py').exists():
        print("❌ Please run this script from the BOWEN Framework directory")
        sys.exit(1)
    
    steps = [
        ("Create .env file", create_env_file),
        ("Setup directories", setup_directories),
        ("Install dependencies", install_dependencies),
        ("Configure API key", setup_api_key),
        ("Test configuration", test_configuration)
    ]
    
    success_count = 0
    
    for step_name, step_func in steps:
        print(f"\n🔄 {step_name}...")
        if step_func():
            success_count += 1
        else:
            print(f"❌ {step_name} failed")
    
    print(f"\n{'='*50}")
    print(f"Setup Results: {success_count}/{len(steps)} steps completed")
    
    if success_count == len(steps):
        print("🎉 BOWEN Framework setup complete!")
        print("\nNext steps:")
        print("1. Run: python cli.py")
        print("2. Try: /help")
        print("3. Test: 'Create a strategic roadmap'")
    else:
        print("⚠️  Setup completed with some issues")
        print("Check the error messages above and try again")

if __name__ == "__main__":
    main()