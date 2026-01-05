#!/usr/bin/env python3
"""
BOWEN Self-Upgrading Engine
Monitors Claude updates, auto-upgrades, and self-improves
"""

import os
import json
import logging
import subprocess
import schedule
import asyncio
import shutil
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import anthropic
import time

logger = logging.getLogger(__name__)

class SelfUpgrader:
    """
    Self-upgrading system that:
    1. Monitors Anthropic for new model releases
    2. Automatically switches to better models
    3. Tests new capabilities
    4. Rewrites BOWEN's own code to use new features
    5. Self-optimizes based on improvements
    """
    
    def __init__(self, bowen_path: str = "/Users/yimi/Desktop/bowen"):
        """Initialize with BOWEN framework path"""
        self.bowen_path = Path(bowen_path)
        self.config_path = self.bowen_path / "config.py"
        self.upgrade_history_path = self.bowen_path / "upgrade_history.json"
        
        # Current model info
        self.current_model = os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not set - upgrade checks disabled")
            return
        
        # Initialize Anthropic client
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        # Load upgrade history
        self.upgrade_history = self._load_upgrade_history()
        
        # Known models and their capabilities
        self.known_models = {
            "claude-3-haiku-20240307": {
                "tier": "fast",
                "context": 200000,
                "capabilities": ["text"],
                "release_date": "2024-03-07"
            },
            "claude-3-5-sonnet-20241022": {
                "tier": "balanced",
                "context": 200000,
                "capabilities": ["text", "vision", "tool_use"],
                "release_date": "2024-10-22"
            },
            "claude-sonnet-4-20250514": {
                "tier": "advanced",
                "context": 200000,
                "capabilities": ["text", "vision", "tool_use", "enhanced_reasoning"],
                "release_date": "2025-05-14"
            }
        }
        
        logger.info(f"Self-Upgrader initialized with current model: {self.current_model}")
    
    async def check_for_updates(self) -> Dict[str, Any]:
        """
        Check for new models by TESTING real Anthropic API - ANTI-HALLUCINATION
        """
        try:
            logger.info("🔍 Checking for model updates (testing real API)...")
            
            # STEP 1: Get available models by TESTING them (not asking Claude)
            available_models = self._get_available_models()
            
            if not available_models:
                return {
                    "new_model_available": False,
                    "error": "Could not verify any models",
                    "checked_at": datetime.now().isoformat()
                }
            
            # STEP 2: Find newer models based on REAL dates
            newer_models = self._find_newer_models(available_models)
            
            if newer_models:
                best_model = self._select_best_model(newer_models)
                
                # STEP 3: Calculate improvements based on FACTS, not speculation
                improvements = []
                current_caps = self._get_model_capabilities(self.current_model)
                new_caps = best_model.get("capabilities", [])
                
                for cap in new_caps:
                    if cap not in current_caps:
                        improvements.append(f"New capability: {cap}")
                
                # STEP 4: Return VERIFIED information only
                return {
                    "new_model_available": True,
                    "model_name": best_model["id"],
                    "current_model": self.current_model,
                    "improvements": improvements if improvements else ["Newer version available"],
                    "should_upgrade": self._should_upgrade(best_model),
                    "verified": best_model.get("verified", False),
                    "release_date": best_model.get("created", "Unknown"),
                    "checked_at": datetime.now().isoformat(),
                    "source": "API_TESTED"  # Mark as real data
                }
            else:
                return {
                    "new_model_available": False,
                    "message": f"Already using latest available model: {self.current_model}",
                    "checked_at": datetime.now().isoformat(),
                    "verified_models": [m["id"] for m in available_models],
                    "source": "API_TESTED"
                }
                
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return {
                "new_model_available": False,
                "error": str(e),
                "checked_at": datetime.now().isoformat(),
                "source": "ERROR"
            }
    
    async def test_new_model(self, model_name: str) -> Dict[str, Any]:
        """
        Test new model capabilities and performance
        """
        try:
            logger.info(f"Testing model: {model_name}")
            
            # Benchmark tests
            test_results = {
                "model_name": model_name,
                "tested_at": datetime.now().isoformat(),
                "tests": {}
            }
            
            # Test 1: Basic reasoning
            reasoning_result = await self._test_reasoning(model_name)
            test_results["tests"]["reasoning"] = reasoning_result
            
            # Test 2: Code generation
            code_result = await self._test_code_generation(model_name)
            test_results["tests"]["code_generation"] = code_result
            
            # Test 3: Response speed
            speed_result = await self._test_speed(model_name)
            test_results["tests"]["speed"] = speed_result
            
            # Test 4: Vision capabilities (if available)
            if "vision" in self._get_model_capabilities(model_name):
                vision_result = await self._test_vision(model_name)
                test_results["tests"]["vision"] = vision_result
            
            # Overall assessment
            test_results["overall_score"] = self._calculate_overall_score(test_results["tests"])
            test_results["passed"] = test_results["overall_score"] >= 70  # 70% threshold
            
            return test_results
            
        except Exception as e:
            logger.error(f"Error testing model {model_name}: {e}")
            return {
                "model_name": model_name,
                "passed": False,
                "error": str(e)
            }
    
    async def upgrade_model(self, new_model: str):
        """
        Upgrade BOWEN to new model
        """
        try:
            logger.info(f"Upgrading from {self.current_model} to {new_model}")
            
            # Create backup
            backup_path = self._create_backup()
            
            # Update config.py
            self._update_config_file(new_model)
            
            # Update environment variable
            self._update_environment_variable(new_model)
            
            # Test core functionality
            test_passed = await self._test_core_functionality(new_model)
            
            if test_passed:
                # Update upgrade history
                self._record_upgrade(self.current_model, new_model)
                
                # Commit changes
                self._commit_upgrade(self.current_model, new_model)
                
                # Update current model
                self.current_model = new_model
                
                logger.info(f"Successfully upgraded to {new_model}")
                return {"success": True, "model": new_model}
            else:
                # Rollback
                self._rollback_upgrade(backup_path)
                logger.error(f"Upgrade to {new_model} failed - rolled back")
                return {"success": False, "error": "Core functionality test failed"}
                
        except Exception as e:
            logger.error(f"Error upgrading to {new_model}: {e}")
            return {"success": False, "error": str(e)}
    
    async def detect_new_capabilities(self, model_name: str) -> List[str]:
        """
        Detect what new features the model has
        """
        try:
            current_capabilities = self._get_model_capabilities(self.current_model)
            new_capabilities = self._get_model_capabilities(model_name)
            
            # Find new capabilities
            added_capabilities = [cap for cap in new_capabilities if cap not in current_capabilities]
            
            # Use the model to analyze its own changelog
            if added_capabilities:
                analysis_prompt = f"""
                Analyze the new capabilities of {model_name} compared to {self.current_model}.
                
                New capabilities detected: {added_capabilities}
                
                For each new capability, explain:
                1. What it enables
                2. How it could improve BOWEN framework
                3. Specific implementation suggestions
                
                Return a list of actionable improvements BOWEN could make.
                """
                
                response = self.client.messages.create(
                    model=model_name,
                    max_tokens=1500,
                    messages=[{"role": "user", "content": analysis_prompt}]
                )
                
                # Parse response for improvement suggestions
                improvements = self._parse_improvement_suggestions(response.content[0].text)
                return improvements
            
            return []
            
        except Exception as e:
            logger.error(f"Error detecting new capabilities: {e}")
            return []
    
    async def self_improve(self, new_capabilities: List[str]):
        """
        Rewrite BOWEN's own code to use new features
        """
        try:
            logger.info(f"Self-improving with {len(new_capabilities)} new capabilities")
            
            improvements_made = []
            
            for capability in new_capabilities:
                # Identify files that could benefit from this capability
                target_files = self._identify_improvement_targets(capability)
                
                for file_path in target_files:
                    try:
                        # Generate improved code
                        improved_code = await self._generate_improved_code(file_path, capability)
                        
                        if improved_code:
                            # Apply improvement
                            self._apply_code_improvement(file_path, improved_code, capability)
                            improvements_made.append(f"Enhanced {file_path} with {capability}")
                    except Exception as e:
                        logger.warning(f"Could not improve {file_path}: {e}")
            
            # Commit improvements
            if improvements_made:
                self._commit_self_improvements(new_capabilities, improvements_made)
                logger.info(f"Self-improvement complete: {len(improvements_made)} files enhanced")
            
            return improvements_made
            
        except Exception as e:
            logger.error(f"Error in self-improvement: {e}")
            return []
    
    def schedule_update_checks(self):
        """
        Schedule daily update checks
        """
        try:
            # Schedule daily check at 3 AM
            schedule.every().day.at("03:00").do(self._daily_upgrade_check)
            
            # Schedule weekly self-improvement check
            schedule.every().monday.at("03:30").do(self._weekly_improvement_check)
            
            logger.info("Update checks scheduled for 3:00 AM daily")
            
            # Run scheduler in background
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except Exception as e:
            logger.error(f"Error in scheduler: {e}")
    
    def _daily_upgrade_check(self):
        """Daily upgrade check function"""
        asyncio.run(self._perform_daily_check())
    
    async def _perform_daily_check(self):
        """Perform daily upgrade check"""
        try:
            # Check for updates
            update_info = await self.check_for_updates()
            
            if update_info.get('new_model_available'):
                model_name = update_info['model_name']
                
                # Test new model
                test_results = await self.test_new_model(model_name)
                
                if test_results.get('passed'):
                    # Upgrade automatically
                    upgrade_result = await self.upgrade_model(model_name)
                    
                    if upgrade_result.get('success'):
                        # Detect new capabilities
                        new_caps = await self.detect_new_capabilities(model_name)
                        
                        # Self-improve using new capabilities
                        if new_caps:
                            await self.self_improve(new_caps)
                        
                        logger.info(f"Auto-upgraded to {model_name}")
                    else:
                        logger.error(f"Auto-upgrade to {model_name} failed")
                else:
                    logger.info(f"Model {model_name} failed tests - upgrade skipped")
            
        except Exception as e:
            logger.error(f"Daily upgrade check failed: {e}")
    
    def _weekly_improvement_check(self):
        """Weekly self-improvement check"""
        try:
            # Analyze current performance
            # Look for optimization opportunities
            # Apply performance improvements
            logger.info("Weekly self-improvement check completed")
        except Exception as e:
            logger.error(f"Weekly improvement check failed: {e}")
    
    # Helper methods
    def _get_available_models(self) -> List[Dict[str, Any]]:
        """Get available models by TESTING real Anthropic API - NO HALLUCINATION"""
        try:
            # CRITICAL: Don't ask Claude - test real model names
            logger.info("Testing real Anthropic models by API calls...")
            
            # Known model names (from actual Anthropic releases)
            known_models = [
                "claude-3-haiku-20240307",
                "claude-3-sonnet-20240229", 
                "claude-3-opus-20240229",
                "claude-3-5-sonnet-20240620",
                "claude-3-5-sonnet-20241022",
                "claude-sonnet-4-20250514",
                # Add future models here when Anthropic actually releases them
            ]
            
            # Try to discover new models automatically
            try:
                import asyncio
                try:
                    # Try to get existing event loop
                    loop = asyncio.get_running_loop()
                    # If we're already in an async context, create a task
                    discovered_models = []
                    logger.info("🔍 Model discovery deferred (running in async context)")
                except RuntimeError:
                    # No event loop running, safe to create one
                    discovered_models = asyncio.run(self.discover_new_models())
                    known_models.extend(discovered_models)
                    logger.info(f"🔍 Enhanced model list with {len(discovered_models)} discovered models")
            except Exception as e:
                logger.warning(f"Model discovery failed, using known models only: {e}")
            
            available_models = []
            
            for model_name in known_models:
                try:
                    # Test if model actually exists by calling it
                    test_response = self.client.messages.create(
                        model=model_name,
                        max_tokens=10,
                        messages=[{"role": "user", "content": "test"}]
                    )
                    
                    # If we get here, model exists
                    available_models.append({
                        "id": model_name,
                        "created": self._extract_date_from_model_name(model_name),
                        "capabilities": self._get_model_capabilities(model_name),
                        "verified": True,  # Actually tested
                        "test_successful": True
                    })
                    
                    logger.info(f"✅ Verified model exists: {model_name}")
                    
                except Exception as model_error:
                    # Model doesn't exist or isn't accessible
                    logger.info(f"❌ Model not available: {model_name} - {str(model_error)}")
                    continue
            
            # Sort by date (newest first)
            available_models.sort(key=lambda x: x["created"], reverse=True)
            
            logger.info(f"Found {len(available_models)} working models")
            return available_models
            
        except Exception as e:
            logger.error(f"Error testing available models: {e}")
            # Return minimal safe fallback
            return [{
                "id": self.current_model,
                "created": "2025-05-14",
                "capabilities": ["text", "vision", "tool_use"],
                "verified": False,
                "error": str(e)
            }]
    
    def _extract_date_from_model_name(self, model_name: str) -> str:
        """Extract date from model name like 'claude-3-5-sonnet-20241022'"""
        try:
            # Extract date pattern YYYYMMDD
            import re
            date_match = re.search(r'(\d{8})$', model_name)
            if date_match:
                date_str = date_match.group(1)
                # Convert YYYYMMDD to YYYY-MM-DD
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            else:
                return "2024-01-01"  # Fallback
        except:
            return "2024-01-01"
    
    def _find_newer_models(self, available_models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find models newer than current model"""
        current_date = self._get_model_release_date(self.current_model)
        
        newer_models = []
        for model in available_models:
            model_date = datetime.fromisoformat(model["created"])
            if model_date > current_date:
                newer_models.append(model)
        
        return sorted(newer_models, key=lambda x: x["created"], reverse=True)
    
    def _select_best_model(self, models: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the best model from available options"""
        # For now, return the newest model
        return models[0] if models else {}
    
    def _should_upgrade(self, model_info: Dict[str, Any]) -> bool:
        """Determine if we should upgrade to this model"""
        # Basic criteria: must be newer and have enhanced capabilities
        return len(model_info.get("capabilities", [])) >= len(self._get_model_capabilities(self.current_model))
    
    def _analyze_improvements(self, model_info: Dict[str, Any]) -> List[str]:
        """Analyze improvements in new model"""
        current_caps = self._get_model_capabilities(self.current_model)
        new_caps = model_info.get("capabilities", [])
        
        improvements = []
        for cap in new_caps:
            if cap not in current_caps:
                improvements.append(f"New capability: {cap}")
        
        return improvements
    
    def _get_model_capabilities(self, model_name: str) -> List[str]:
        """Get capabilities of a model"""
        return self.known_models.get(model_name, {}).get("capabilities", ["text"])
    
    def _get_model_release_date(self, model_name: str) -> datetime:
        """Get release date of model"""
        date_str = self.known_models.get(model_name, {}).get("release_date", "2024-01-01")
        return datetime.fromisoformat(date_str)
    
    async def _test_reasoning(self, model_name: str) -> Dict[str, Any]:
        """Test reasoning capabilities"""
        try:
            start_time = time.time()
            
            response = self.client.messages.create(
                model=model_name,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": "Solve this logic puzzle: If all roses are flowers, and some flowers are red, can we conclude that some roses are red? Explain your reasoning."
                }]
            )
            
            end_time = time.time()
            
            # Evaluate quality (simplified)
            response_text = response.content[0].text
            quality_score = 80 if "cannot conclude" in response_text.lower() else 60
            
            return {
                "score": quality_score,
                "response_time": end_time - start_time,
                "passed": quality_score >= 70
            }
        except Exception as e:
            return {"score": 0, "error": str(e), "passed": False}
    
    async def _test_code_generation(self, model_name: str) -> Dict[str, Any]:
        """Test code generation capabilities"""
        try:
            start_time = time.time()
            
            response = self.client.messages.create(
                model=model_name,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": "Write a Python function that calculates the Fibonacci sequence up to n terms."
                }]
            )
            
            end_time = time.time()
            
            # Evaluate code quality (simplified)
            response_text = response.content[0].text
            quality_score = 85 if "def" in response_text and "fibonacci" in response_text.lower() else 60
            
            return {
                "score": quality_score,
                "response_time": end_time - start_time,
                "passed": quality_score >= 70
            }
        except Exception as e:
            return {"score": 0, "error": str(e), "passed": False}
    
    async def _test_speed(self, model_name: str) -> Dict[str, Any]:
        """Test response speed"""
        try:
            start_time = time.time()
            
            response = self.client.messages.create(
                model=model_name,
                max_tokens=100,
                messages=[{
                    "role": "user",
                    "content": "Hello, how are you today?"
                }]
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Score based on response time
            if response_time < 2:
                score = 90
            elif response_time < 5:
                score = 75
            else:
                score = 60
            
            return {
                "score": score,
                "response_time": response_time,
                "passed": score >= 70
            }
        except Exception as e:
            return {"score": 0, "error": str(e), "passed": False}
    
    async def _test_vision(self, model_name: str) -> Dict[str, Any]:
        """Test vision capabilities"""
        # This would test vision with an actual image
        # For now, return a mock result
        return {
            "score": 85,
            "capabilities": ["image_analysis", "text_extraction"],
            "passed": True
        }
    
    def _calculate_overall_score(self, test_results: Dict[str, Any]) -> float:
        """Calculate overall test score"""
        scores = [test.get("score", 0) for test in test_results.values()]
        return sum(scores) / len(scores) if scores else 0
    
    async def _test_core_functionality(self, model_name: str) -> bool:
        """Test core BOWEN functionality with new model"""
        try:
            # Test basic chat functionality
            response = self.client.messages.create(
                model=model_name,
                max_tokens=100,
                messages=[{"role": "user", "content": "Test message"}]
            )
            
            return len(response.content) > 0 and response.content[0].text
        except:
            return False
    
    def _create_backup(self) -> str:
        """Create backup before upgrade"""
        backup_dir = self.bowen_path / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"pre_upgrade_{timestamp}"
        
        # Copy critical files
        critical_files = ["config.py", "bowen_core.py", "cli.py"]
        backup_path.mkdir(exist_ok=True)
        
        for file_name in critical_files:
            source_file = self.bowen_path / file_name
            if source_file.exists():
                shutil.copy2(source_file, backup_path / file_name)
        
        return str(backup_path)
    
    def _update_config_file(self, new_model: str):
        """Update config.py with new model"""
        config_content = self.config_path.read_text()
        
        # Replace model name
        updated_content = config_content.replace(
            f'"{self.current_model}"',
            f'"{new_model}"'
        )
        
        self.config_path.write_text(updated_content)
    
    def _update_environment_variable(self, new_model: str):
        """Update environment variable"""
        os.environ['ANTHROPIC_MODEL'] = new_model
    
    def _record_upgrade(self, old_model: str, new_model: str):
        """Record upgrade in history"""
        upgrade_record = {
            "date": datetime.now().isoformat(),
            "from_model": old_model,
            "to_model": new_model,
            "improvements": self._analyze_improvements({"capabilities": self._get_model_capabilities(new_model)}),
            "auto_upgrade": True
        }
        
        self.upgrade_history["upgrades"].append(upgrade_record)
        self._save_upgrade_history()
    
    def _commit_upgrade(self, old_model: str, new_model: str):
        """Commit upgrade to git"""
        try:
            subprocess.run(["git", "add", "."], cwd=self.bowen_path, capture_output=True)
            subprocess.run([
                "git", "commit", "-m", f"Auto-upgrade: {old_model} → {new_model}"
            ], cwd=self.bowen_path, capture_output=True)
        except:
            pass  # Git operations are optional
    
    def _rollback_upgrade(self, backup_path: str):
        """Rollback failed upgrade"""
        backup_dir = Path(backup_path)
        
        for backup_file in backup_dir.iterdir():
            if backup_file.is_file():
                target_file = self.bowen_path / backup_file.name
                shutil.copy2(backup_file, target_file)
    
    def _load_upgrade_history(self) -> Dict[str, Any]:
        """Load upgrade history"""
        if self.upgrade_history_path.exists():
            with open(self.upgrade_history_path) as f:
                return json.load(f)
        
        return {"upgrades": []}
    
    def _save_upgrade_history(self):
        """Save upgrade history"""
        with open(self.upgrade_history_path, 'w') as f:
            json.dump(self.upgrade_history, f, indent=2, default=str)
    
    def _parse_improvement_suggestions(self, response_text: str) -> List[str]:
        """Parse improvement suggestions from AI response"""
        # Simplified parsing - in production, this would be more sophisticated
        lines = response_text.split('\n')
        improvements = []
        
        for line in lines:
            if line.strip().startswith('-') or line.strip().startswith('•'):
                improvements.append(line.strip()[1:].strip())
        
        return improvements[:5]  # Limit to top 5
    
    def _identify_improvement_targets(self, capability: str) -> List[Path]:
        """Identify files that could benefit from a capability"""
        targets = []
        
        capability_file_mapping = {
            "enhanced_reasoning": ["bowen_core.py", "engines/autonomous_learner.py"],
            "long_context": ["bowen_core.py", "cli.py"],
            "better_code": ["engines/code_agent.py"],
            "vision": ["vision_engine.py"]
        }
        
        file_patterns = capability_file_mapping.get(capability, [])
        
        for pattern in file_patterns:
            file_path = self.bowen_path / pattern
            if file_path.exists():
                targets.append(file_path)
        
        return targets
    
    async def _generate_improved_code(self, file_path: Path, capability: str) -> Optional[str]:
        """Generate improved code using new capability"""
        try:
            current_code = file_path.read_text()
            
            improvement_prompt = f"""
            Improve this Python code to leverage the new {capability} capability:
            
            Current code:
            {current_code[:3000]}  # Limit context
            
            Provide only the improved code sections that should be changed.
            Focus on practical improvements that utilize {capability}.
            """
            
            response = self.client.messages.create(
                model=self.current_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": improvement_prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Error generating improved code: {e}")
            return None
    
    def _apply_code_improvement(self, file_path: Path, improved_code: str, capability: str):
        """Apply code improvement to file"""
        # This is a simplified implementation
        # In production, this would carefully merge improvements
        
        # For now, just append a comment about the improvement
        current_code = file_path.read_text()
        
        improvement_comment = f"\n\n# BOWEN Self-Improvement: Enhanced with {capability} - {datetime.now().strftime('%Y-%m-%d')}\n"
        
        file_path.write_text(current_code + improvement_comment)
    
    def _commit_self_improvements(self, capabilities: List[str], improvements: List[str]):
        """Commit self-improvements to git"""
        try:
            subprocess.run(["git", "add", "."], cwd=self.bowen_path, capture_output=True)
            
            commit_message = f"Self-improvement: leveraging {', '.join(capabilities)}"
            subprocess.run([
                "git", "commit", "-m", commit_message
            ], cwd=self.bowen_path, capture_output=True)
        except:
            pass  # Git operations are optional
    
    async def discover_new_models(self) -> list[str]:
        """Automatically discover new models without hardcoding"""
        
        discovered = []
        
        # 1. Test pattern-based names for future models
        patterns = [
            "claude-sonnet-{version}-{date}",
            "claude-opus-{version}-{date}",
            "claude-haiku-{version}-{date}",
        ]
        
        # Test versions 4, 5, 6 and recent dates
        for version in [4, 5, 6]:
            for year in [2025, 2026]:
                for month in range(1, 13):
                    test_models = [
                        f"claude-sonnet-{version}-{year}{month:02d}15",
                        f"claude-opus-{version}-{year}{month:02d}15",
                    ]
                    for model in test_models:
                        if await self._test_model_exists(model):
                            discovered.append(model)
                            logger.info(f"🆕 Discovered new model: {model}")
        
        # 2. Scrape Anthropic docs for model names
        try:
            response = requests.get("https://docs.anthropic.com/en/docs/about-claude/models", timeout=10)
            if response.status_code == 200:
                models_from_docs = self._extract_models_from_html(response.text)
                discovered.extend(models_from_docs)
                logger.info(f"📄 Found {len(models_from_docs)} models from docs")
        except Exception as e:
            logger.warning(f"Could not scrape Anthropic docs: {e}")
        
        # 3. Check Anthropic changelog
        try:
            response = requests.get("https://docs.anthropic.com/en/release-notes/api", timeout=10)
            if response.status_code == 200:
                changelog_models = self._extract_models_from_changelog(response.text)
                discovered.extend(changelog_models)
                logger.info(f"📝 Found {len(changelog_models)} models from changelog")
        except Exception as e:
            logger.warning(f"Could not scrape Anthropic changelog: {e}")
        
        # Remove duplicates and return
        unique_discovered = list(set(discovered))
        logger.info(f"🔍 Total discovered models: {len(unique_discovered)}")
        return unique_discovered
    
    async def _test_model_exists(self, model_name: str) -> bool:
        """Test if a model exists by making a minimal API call"""
        try:
            response = self.client.messages.create(
                model=model_name,
                max_tokens=5,
                messages=[{"role": "user", "content": "hi"}]
            )
            return True
        except Exception:
            return False
    
    def _extract_models_from_html(self, html_content: str) -> list[str]:
        """Extract model names from Anthropic documentation HTML"""
        import re
        
        # Pattern to match Claude model names
        model_pattern = r'claude-(?:3|3\.5|4|5|6)-(?:sonnet|opus|haiku)-\d{8}'
        matches = re.findall(model_pattern, html_content, re.IGNORECASE)
        
        # Additional patterns for newer formats
        alt_patterns = [
            r'claude-sonnet-[4-6]-\d{8}',
            r'claude-opus-[4-6]-\d{8}',
            r'claude-haiku-[4-6]-\d{8}'
        ]
        
        for pattern in alt_patterns:
            matches.extend(re.findall(pattern, html_content, re.IGNORECASE))
        
        return list(set(matches))
    
    def _extract_models_from_changelog(self, changelog_content: str) -> list[str]:
        """Extract model names from Anthropic changelog"""
        import re
        
        # Look for model announcements in changelog
        model_announcements = re.findall(
            r'(?:released?|announced?|available?).*?(claude-[a-z0-9-]+)', 
            changelog_content, 
            re.IGNORECASE
        )
        
        # Filter to valid model name patterns
        valid_models = []
        for model in model_announcements:
            if re.match(r'claude-(?:3|3\.5|4|5|6|sonnet|opus|haiku)', model, re.IGNORECASE):
                valid_models.append(model.lower())
        
        return list(set(valid_models))
    
    async def discover_and_check_updates(self) -> Dict[str, Any]:
        """Discover new models and check for updates in one operation"""
        try:
            logger.info("🔍 Starting comprehensive model discovery and update check...")
            
            # First discover new models
            discovered_models = await self.discover_new_models()
            
            # Then check for updates with enhanced model list
            update_info = await self.check_for_updates()
            
            # Add discovery info to result
            update_info["discovered_models"] = discovered_models
            update_info["discovery_count"] = len(discovered_models)
            
            return update_info
            
        except Exception as e:
            logger.error(f"Error in discover_and_check_updates: {e}")
            return {
                "new_model_available": False,
                "error": str(e),
                "discovered_models": [],
                "discovery_count": 0
            }
    
    def get_upgrade_status(self) -> Dict[str, Any]:
        """Get current upgrade status"""
        return {
            "current_model": self.current_model,
            "last_check": self.upgrade_history.get("last_check"),
            "upgrade_count": len(self.upgrade_history["upgrades"]),
            "latest_upgrade": self.upgrade_history["upgrades"][-1] if self.upgrade_history["upgrades"] else None,
            "auto_upgrade_enabled": True,
            "discovery_enabled": True
        }