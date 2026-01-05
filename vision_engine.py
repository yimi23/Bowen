"""
BOWEN Framework - Vision Engine
Screen capture + Claude Vision analysis for complete visual intelligence

This engine enables BOWEN to:
- Capture screenshots on command
- Analyze visual content with Claude Vision
- Read homework problems from screen
- Debug code errors from screenshots
- Review documents and diagrams
- Understand charts and visual data
"""

import base64
import io
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import pyautogui
from PIL import Image, ImageGrab
import anthropic

logger = logging.getLogger(__name__)

class VisionEngine:
    """
    Complete vision integration for BOWEN Framework
    Handles screen capture and visual analysis using Claude Vision
    """
    
    def __init__(self):
        """Initialize vision engine with Claude Vision capabilities"""
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.vision_model = "claude-3-haiku-20240307"  # Working model for vision analysis
        self.screenshots_dir = Path.home() / "Desktop" / "bowen_outputs" / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Vision analysis contexts for different use cases
        self.analysis_contexts = {
            'homework': "Analyze this homework problem or assignment. Explain what's being asked and provide guidance on how to approach solving it. Don't just give the answer - help me understand the concepts.",
            
            'code': "Analyze this code or error message. Identify any bugs, syntax issues, or logical problems. Explain what's wrong and how to fix it. If it's working code, explain what it does.",
            
            'document': "Read and summarize this document or text. Extract key information, main points, and any important details I should know about.",
            
            'exam': "This is an exam question or study material. Help me understand the concepts being tested and explain the correct approach to answer this type of question.",
            
            'business': "Analyze this business document, chart, or interface. Extract key metrics, insights, and actionable information for decision making.",
            
            'general': "Analyze this image and tell me what you see. Provide detailed observations and any relevant insights."
        }
        
        # Test screen capture permissions
        self.screen_capture_available = True
        try:
            # Test a minimal screen capture
            test_screenshot = ImageGrab.grab(bbox=(0, 0, 1, 1))
            logger.info("VisionEngine initialized with screen capture and Claude Vision capabilities")
        except Exception as e:
            self.screen_capture_available = False
            logger.warning(f"Screen capture permissions not available: {e}")
            logger.info("VisionEngine initialized with Claude Vision (screen capture disabled)")
    
    def capture_screen(self, save_file: bool = True) -> str:
        """
        Capture current screen as base64 encoded image
        
        Args:
            save_file: Whether to save screenshot to disk
            
        Returns:
            Base64 encoded image string
        """
        try:
            if not self.screen_capture_available:
                raise Exception("Screen capture not available - permissions required")
                
            logger.info("REAL SCREEN CAPTURE: Taking screenshot...")
            
            # Capture screen using PIL (more reliable than pyautogui)
            screenshot = ImageGrab.grab()
            
            # Convert to base64
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG')
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Optionally save to disk
            if save_file:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"screenshot_{timestamp}.png"
                filepath = self.screenshots_dir / filename
                screenshot.save(filepath)
                logger.info(f"Screenshot saved: {filepath}")
            
            logger.info("✅ Screen capture successful")
            return image_data
            
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            raise Exception(f"Failed to capture screen: {str(e)}")
    
    def capture_window(self, window_title: str = None) -> str:
        """
        Capture specific window instead of full screen
        
        Args:
            window_title: Title of window to capture (if None, captures active window)
            
        Returns:
            Base64 encoded image string
        """
        try:
            if window_title:
                # Find window by title (platform specific implementation)
                # For now, fall back to full screen capture
                logger.warning("Window-specific capture not implemented, using full screen")
                return self.capture_screen()
            else:
                # Capture active window
                return self.capture_screen()
                
        except Exception as e:
            logger.error(f"Window capture failed: {e}")
            raise Exception(f"Failed to capture window: {str(e)}")
    
    def analyze_with_vision(self, image_data: str, query: str, context: str = 'general') -> str:
        """
        Analyze image using Claude Vision
        
        Args:
            image_data: Base64 encoded image
            query: User's specific question about the image
            context: Type of analysis (homework, code, document, etc.)
            
        Returns:
            Claude's analysis of the image
        """
        try:
            logger.info(f"CLAUDE VISION ANALYSIS: {context} context")
            
            # Build context-specific system prompt
            system_prompt = self.analysis_contexts.get(context, self.analysis_contexts['general'])
            
            # Enhanced prompt with user query
            full_prompt = f"""
{system_prompt}

User's specific question: {query}

Please provide a detailed, helpful analysis that addresses their question while being educational and actionable.
"""
            
            # Call Claude Vision API
            response = self.client.messages.create(
                model=self.vision_model,
                max_tokens=2000,
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data
                            }
                        },
                        {
                            "type": "text", 
                            "text": full_prompt
                        }
                    ]
                }]
            )
            
            logger.info("✅ Claude Vision analysis completed")
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Claude Vision analysis failed: {e}")
            return f"Vision analysis failed: {str(e)}"
    
    def quick_screenshot_analysis(self, query: str, context: str = 'general') -> str:
        """
        Capture screen and analyze in one command
        
        Args:
            query: What to analyze in the screenshot
            context: Type of analysis context
            
        Returns:
            Combined capture + analysis result
        """
        try:
            # Capture screen
            image_data = self.capture_screen()
            
            # Analyze with Claude Vision
            analysis = self.analyze_with_vision(image_data, query, context)
            
            return f"📸 **Screenshot Analysis:**\n\n{analysis}"
            
        except Exception as e:
            return f"❌ Screenshot analysis failed: {str(e)}"
    
    def analyze_homework(self, query: str = "Help me understand this problem") -> str:
        """Quick homework analysis from screenshot"""
        return self.quick_screenshot_analysis(query, 'homework')
    
    def analyze_code(self, query: str = "What's wrong with this code?") -> str:
        """Quick code analysis from screenshot"""
        return self.quick_screenshot_analysis(query, 'code')
    
    def analyze_document(self, query: str = "Summarize this document") -> str:
        """Quick document analysis from screenshot"""
        return self.quick_screenshot_analysis(query, 'document')
    
    def analyze_exam(self, query: str = "Help me understand this exam question") -> str:
        """Quick exam question analysis from screenshot"""
        return self.quick_screenshot_analysis(query, 'exam')
    
    def analyze_business(self, query: str = "Extract key insights from this") -> str:
        """Quick business document analysis from screenshot"""
        return self.quick_screenshot_analysis(query, 'business')
    
    def get_vision_capabilities(self) -> Dict[str, str]:
        """Return available vision analysis capabilities"""
        return {
            '/capture': 'Take screenshot and analyze with custom query',
            '/homework': 'Analyze homework problems (explains concepts, doesn\'t just give answers)',
            '/code': 'Debug code errors and explain solutions',
            '/document': 'Read and summarize documents or text',
            '/exam': 'Help understand exam questions and study materials',
            '/business': 'Analyze business documents, charts, and metrics'
        }
    
    def analyze_from_file(self, image_path: str, query: str, context: str = 'general') -> str:
        """
        Analyze image from file path instead of screenshot
        
        Args:
            image_path: Path to image file
            query: Analysis question
            context: Analysis context
            
        Returns:
            Analysis result
        """
        try:
            # Load and encode image
            with open(image_path, 'rb') as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Analyze with Claude Vision
            analysis = self.analyze_with_vision(image_data, query, context)
            
            return f"📁 **Image Analysis ({Path(image_path).name}):**\n\n{analysis}"
            
        except Exception as e:
            return f"❌ Image analysis failed: {str(e)}"

# Vision command handlers for CLI integration
def handle_capture_command(args: str = "") -> str:
    """Handle /capture command"""
    vision = VisionEngine()
    
    # Parse arguments
    parts = args.strip().split(' ', 1)
    context = 'general'
    query = "What do you see in this screenshot?"
    
    if len(parts) >= 1 and parts[0] in ['homework', 'code', 'document', 'exam', 'business']:
        context = parts[0]
        query = parts[1] if len(parts) > 1 else f"Analyze this {context}"
    elif args:
        query = args
    
    return vision.quick_screenshot_analysis(query, context)

def handle_homework_command(args: str = "") -> str:
    """Handle /homework command"""
    vision = VisionEngine()
    query = args if args else "Help me understand this homework problem"
    return vision.analyze_homework(query)

def handle_code_command(args: str = "") -> str:
    """Handle /code command"""
    vision = VisionEngine()
    query = args if args else "What's wrong with this code?"
    return vision.analyze_code(query)

def handle_document_command(args: str = "") -> str:
    """Handle /document command"""
    vision = VisionEngine()
    query = args if args else "Summarize this document"
    return vision.analyze_document(query)

def handle_exam_command(args: str = "") -> str:
    """Handle /exam command"""
    vision = VisionEngine()
    query = args if args else "Help me understand this exam question"
    return vision.analyze_exam(query)

def handle_business_command(args: str = "") -> str:
    """Handle /business command"""
    vision = VisionEngine()
    query = args if args else "Extract key insights from this business document"
    return vision.analyze_business(query)