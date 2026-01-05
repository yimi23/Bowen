"""
Action Validator: Ensures BOWEN never lies about taking actions
If it says it did something, it MUST have actually done it.
"""

import re
from typing import Dict, Any

class ActionValidator:
    def __init__(self, vision_engine, computer_tools, research_engine):
        self.vision = vision_engine
        self.computer = computer_tools
        self.research = research_engine
        
        # Map of action claims to actual functions
        self.action_map = {
            'screenshot': self._handle_screenshot,
            'capture.*screen': self._handle_screenshot,
            'take.*screenshot': self._handle_screenshot,
            'search.*web': self._handle_web_search,
            'create.*file': self._handle_file_create,
            'save.*file': self._handle_file_create,
            'run.*command': self._handle_command,
            'execute': self._handle_command
        }
    
    def validate_and_execute(self, response_text: str, context: Dict[str, Any]) -> tuple[str, bool]:
        """
        Check if response claims actions. If yes, execute them.
        Returns: (modified_response, actions_executed)
        """
        
        claimed_actions = self._detect_claimed_actions(response_text)
        
        if not claimed_actions:
            # No action claims - response is fine
            return response_text, False
        
        # CRITICAL: If actions are claimed, they MUST be executed
        executed_actions = []
        failed_actions = []
        
        for action_type, action_details in claimed_actions:
            try:
                result = self._execute_action(action_type, action_details, context)
                executed_actions.append({
                    'action': action_type,
                    'result': result
                })
            except Exception as e:
                failed_actions.append({
                    'action': action_type,
                    'error': str(e)
                })
        
        # Modify response to reflect what ACTUALLY happened
        if failed_actions:
            # Don't claim success if we failed
            response_text = self._replace_claims_with_reality(
                response_text, 
                executed_actions, 
                failed_actions
            )
        
        return response_text, len(executed_actions) > 0
    
    def _detect_claimed_actions(self, text: str) -> list:
        """Find all action claims in the response"""
        claims = []
        
        # Patterns that indicate action claims
        action_patterns = [
            (r'(?:I have|I\'ve|I will|I\'ll) (?:captured|taken|saved|created|executed) (?:a )?(\w+)', 'past_action'),
            (r'(?:capturing|taking|saving|creating|executing) (?:a )?(\w+)', 'present_action'),
            (r'screenshot (?:captured|taken|saved)', 'screenshot'),
            (r'file (?:created|saved)', 'file_create'),
            (r'command (?:executed|run)', 'command')
        ]
        
        for pattern, action_type in action_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                claims.append((action_type, match.group(0)))
        
        return claims
    
    def _execute_action(self, action_type: str, details: str, context: Dict) -> Any:
        """Actually execute the claimed action"""
        
        for pattern, handler in self.action_map.items():
            if re.search(pattern, action_type, re.IGNORECASE) or re.search(pattern, details, re.IGNORECASE):
                return handler(context)
        
        raise ValueError(f"Unknown action type: {action_type}")
    
    def _handle_screenshot(self, context: Dict) -> str:
        """Actually take a screenshot"""
        if self.vision:
            screenshot_path = self.vision.capture_screen()
            return f"Screenshot saved to: {screenshot_path}"
        else:
            raise RuntimeError("Vision engine not available")
    
    def _handle_web_search(self, context: Dict) -> str:
        """Actually search the web"""
        query = context.get('query', '')
        if not query:
            raise ValueError("No search query provided")
        
        if self.research:
            results = self.research.search(query)
            return f"Found {len(results)} results"
        else:
            raise RuntimeError("Research engine not available")
    
    def _handle_file_create(self, context: Dict) -> str:
        """Actually create a file"""
        filename = context.get('filename', 'output.txt')
        content = context.get('content', '')
        
        if self.computer:
            path = self.computer.create_file(filename, content)
            return f"File created: {path}"
        else:
            raise RuntimeError("Computer tools not available")
    
    def _handle_command(self, context: Dict) -> str:
        """Actually run a command"""
        command = context.get('command', '')
        if not command:
            raise ValueError("No command provided")
        
        if self.computer:
            result = self.computer.execute_command(command)
            return f"Command executed: {result}"
        else:
            raise RuntimeError("Computer tools not available")
    
    def _replace_claims_with_reality(self, text: str, executed: list, failed: list) -> str:
        """Replace fake claims with what actually happened"""
        
        # Remove theatrical asterisk actions
        text = re.sub(r'\*[^*]+\*', '', text)
        
        # Add reality footer
        if executed:
            text += "\n\n✅ Actions taken:\n"
            for action in executed:
                text += f"  • {action['action']}: {action['result']}\n"
        
        if failed:
            text += "\n\n❌ Actions failed:\n"
            for action in failed:
                text += f"  • {action['action']}: {action['error']}\n"
        
        return text.strip()


def block_fake_responses(response: str) -> str:
    """
    Block responses that claim actions without executing them
    """
    
    # Patterns that indicate fake theatrical responses
    fake_patterns = [
        r'\*(?:beeps?|whirs?|activat\w+|perform\w+|execut\w+)[^*]*\*',
        r'(?:I am|I\'m) (?:now )?(?:activating|performing|executing)',
        r'Mr\. Oyimi',
        r'discreetly',
        r'Understood\. I am now'
    ]
    
    for pattern in fake_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            return "I can't actually do that. What do you need help with?"
    
    return response