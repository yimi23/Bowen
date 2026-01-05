#!/usr/bin/env python3
"""
BOWEN Framework Configuration Management
Proper environment variable handling and configuration validation
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class BOWENConfig:
    """
    Centralized configuration management for BOWEN Framework
    Handles environment variables, validation, and defaults
    """
    
    def __init__(self):
        self._validate_required_config()
        
    # ==============================================
    # ANTHROPIC CLAUDE API CONFIGURATION
    # ==============================================
    
    @property
    def anthropic_api_key(self) -> Optional[str]:
        """Get Anthropic API key from environment"""
        return os.getenv('ANTHROPIC_API_KEY')
    
    @property
    def anthropic_model(self) -> str:
        """Get Claude model to use"""
        return os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')
    
    @property
    def anthropic_max_tokens(self) -> int:
        """Get max tokens for Claude API calls"""
        return int(os.getenv('ANTHROPIC_MAX_TOKENS', '1000'))
    
    @property
    def has_anthropic_key(self) -> bool:
        """Check if Anthropic API key is available"""
        key = self.anthropic_api_key
        return key is not None and key.startswith('sk-ant-')
    
    # ==============================================
    # BOWEN FRAMEWORK CONFIGURATION
    # ==============================================
    
    @property
    def debug_mode(self) -> bool:
        """Check if debug mode is enabled"""
        return os.getenv('BOWEN_DEBUG', 'false').lower() == 'true'
    
    @property
    def log_level(self) -> str:
        """Get logging level"""
        return os.getenv('BOWEN_LOG_LEVEL', 'INFO').upper()
    
    @property
    def session_timeout(self) -> int:
        """Get session timeout in seconds"""
        return int(os.getenv('BOWEN_SESSION_TIMEOUT', '3600'))
    
    @property
    def default_personality(self) -> str:
        """Get default personality on startup"""
        return os.getenv('BOWEN_DEFAULT_PERSONALITY', 'captain').lower()
    
    # ==============================================
    # DOCUMENT ENGINE CONFIGURATION
    # ==============================================
    
    @property
    def output_directory(self) -> Path:
        """Get output directory for generated documents"""
        output_dir = os.getenv('BOWEN_OUTPUT_DIR', str(Path.home() / 'Desktop' / 'bowen_outputs'))
        path = Path(output_dir)
        path.mkdir(exist_ok=True)
        return path
    
    @property
    def document_quality(self) -> str:
        """Get document generation quality setting"""
        return os.getenv('DOCUMENT_QUALITY', 'high')
    
    @property
    def chart_dpi(self) -> int:
        """Get DPI for chart generation"""
        return int(os.getenv('CHART_DPI', '300'))
    
    @property
    def excel_auto_fit(self) -> bool:
        """Check if Excel auto-fit is enabled"""
        return os.getenv('EXCEL_AUTO_FIT', 'true').lower() == 'true'
    
    # ==============================================
    # COMPUTER TOOLS CONFIGURATION
    # ==============================================
    
    @property
    def tamara_safe_mode(self) -> bool:
        """Check if TAMARA safe mode is enabled"""
        return os.getenv('TAMARA_SAFE_MODE', 'true').lower() == 'true'
    
    @property
    def tamara_allowed_dirs(self) -> list:
        """Get allowed directories for TAMARA file operations"""
        env_dirs = os.getenv('TAMARA_ALLOWED_DIRS')
        if env_dirs:
            return [d.strip() for d in env_dirs.split(',')]
        else:
            return [
                str(Path.home() / 'Desktop'),
                str(Path.home() / 'Documents'),
                str(Path.home() / 'Downloads'),
                '/tmp',
                '/var/folders'  # macOS temp
            ]
    
    @property
    def bash_timeout(self) -> int:
        """Get bash command timeout in seconds"""
        return int(os.getenv('BASH_TIMEOUT', '30'))
    
    # ==============================================
    # MEMORY SYSTEM CONFIGURATION
    # ==============================================
    
    @property
    def max_working_memory(self) -> int:
        """Get maximum working memory items"""
        return int(os.getenv('MAX_WORKING_MEMORY', '10'))
    
    @property
    def max_episodic_memory(self) -> int:
        """Get maximum episodic memory items"""
        return int(os.getenv('MAX_EPISODIC_MEMORY', '100'))
    
    @property
    def max_semantic_memory(self) -> int:
        """Get maximum semantic memory items"""
        return int(os.getenv('MAX_SEMANTIC_MEMORY', '500'))
    
    # Vector database configuration (future)
    @property
    def vector_db_url(self) -> Optional[str]:
        """Get vector database URL"""
        return os.getenv('VECTOR_DB_URL')
    
    @property
    def vector_db_collection(self) -> str:
        """Get vector database collection name"""
        return os.getenv('VECTOR_DB_COLLECTION', 'bowen_memory')
    
    # ==============================================
    # CLI INTERFACE CONFIGURATION
    # ==============================================
    
    @property
    def enable_colors(self) -> bool:
        """Check if terminal colors are enabled"""
        return os.getenv('ENABLE_COLORS', 'true').lower() == 'true'
    
    @property
    def cli_theme(self) -> str:
        """Get CLI theme"""
        return os.getenv('CLI_THEME', 'professional')
    
    @property
    def command_history_size(self) -> int:
        """Get command history size"""
        return int(os.getenv('COMMAND_HISTORY_SIZE', '1000'))
    
    @property
    def save_session_history(self) -> bool:
        """Check if session history should be saved"""
        return os.getenv('SAVE_SESSION_HISTORY', 'true').lower() == 'true'
    
    # ==============================================
    # DEVELOPMENT CONFIGURATION
    # ==============================================
    
    @property
    def dev_mode(self) -> bool:
        """Check if development mode is enabled"""
        return os.getenv('DEV_MODE', 'false').lower() == 'true'
    
    @property
    def mock_api_responses(self) -> bool:
        """Check if API responses should be mocked"""
        return os.getenv('MOCK_API_RESPONSES', 'false').lower() == 'true'
    
    @property
    def enable_debug_logging(self) -> bool:
        """Check if debug logging is enabled"""
        return os.getenv('ENABLE_DEBUG_LOGGING', 'false').lower() == 'true'
    
    @property
    def test_output_dir(self) -> Path:
        """Get test output directory"""
        test_dir = os.getenv('TEST_OUTPUT_DIR', '/tmp/bowen_test_outputs')
        path = Path(test_dir)
        path.mkdir(exist_ok=True)
        return path
    
    @property
    def cleanup_test_files(self) -> bool:
        """Check if test files should be cleaned up"""
        return os.getenv('CLEANUP_TEST_FILES', 'true').lower() == 'true'
    
    # ==============================================
    # VALIDATION AND UTILITIES
    # ==============================================
    
    def _validate_required_config(self):
        """Validate required configuration"""
        if not self.has_anthropic_key:
            logger.warning("ANTHROPIC_API_KEY not configured - AI features will be disabled")
        
        # Validate personality
        valid_personalities = ['captain', 'tamara', 'helen', 'scout']
        if self.default_personality not in valid_personalities:
            logger.warning(f"Invalid default personality: {self.default_personality}. Using 'captain'")
        
        # Validate directories exist
        if not self.output_directory.exists():
            logger.warning(f"Output directory does not exist: {self.output_directory}")
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration as dictionary"""
        return {
            'anthropic': {
                'api_key_configured': self.has_anthropic_key,
                'model': self.anthropic_model,
                'max_tokens': self.anthropic_max_tokens
            },
            'framework': {
                'debug_mode': self.debug_mode,
                'log_level': self.log_level,
                'session_timeout': self.session_timeout,
                'default_personality': self.default_personality
            },
            'documents': {
                'output_directory': str(self.output_directory),
                'quality': self.document_quality,
                'chart_dpi': self.chart_dpi,
                'excel_auto_fit': self.excel_auto_fit
            },
            'computer_tools': {
                'safe_mode': self.tamara_safe_mode,
                'allowed_dirs': self.tamara_allowed_dirs,
                'bash_timeout': self.bash_timeout
            },
            'memory': {
                'max_working': self.max_working_memory,
                'max_episodic': self.max_episodic_memory,
                'max_semantic': self.max_semantic_memory
            },
            'cli': {
                'colors': self.enable_colors,
                'theme': self.cli_theme,
                'history_size': self.command_history_size,
                'save_history': self.save_session_history
            },
            'development': {
                'dev_mode': self.dev_mode,
                'mock_responses': self.mock_api_responses,
                'debug_logging': self.enable_debug_logging
            }
        }
    
    def print_config_summary(self):
        """Print configuration summary for debugging"""
        print("🔧 BOWEN Framework Configuration")
        print("=" * 40)
        
        print(f"🤖 AI: {'✅ Enabled' if self.has_anthropic_key else '❌ Disabled (no API key)'}")
        print(f"📄 Documents: {self.output_directory}")
        print(f"🛠️  Tools: {'🔒 Safe Mode' if self.tamara_safe_mode else '⚠️  Unrestricted'}")
        print(f"🧠 Memory: Working({self.max_working_memory}) | Episodic({self.max_episodic_memory}) | Semantic({self.max_semantic_memory})")
        print(f"🎨 CLI: Colors({'✅' if self.enable_colors else '❌'}) | Theme({self.cli_theme})")
        print(f"🔍 Debug: {'✅ Enabled' if self.debug_mode else '❌ Disabled'}")

# Global configuration instance
config = BOWENConfig()

# Convenience functions
def get_config() -> BOWENConfig:
    """Get the global configuration instance"""
    return config

def is_ai_enabled() -> bool:
    """Quick check if AI features are available"""
    return config.has_anthropic_key

def get_output_dir() -> Path:
    """Quick access to output directory"""
    return config.output_directory