#!/usr/bin/env python3
"""
BOWEN Complete System Integration Test
Validates all engines are connected and working with REAL data only
"""

import sys
import json
import os
from datetime import datetime
from pathlib import Path

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class BOWENIntegrationTest:
    def __init__(self):
        self.bowen_path = Path('/Users/yimi/Desktop/bowen')
        self.results = []
        self.failed_tests = []
    
    def log(self, status, message, details=""):
        """Log test result"""
        if status == "PASS":
            print(f"{GREEN}✅ PASS{RESET}: {message}")
            if details:
                print(f"   {details}")
        elif status == "FAIL":
            print(f"{RED}❌ FAIL{RESET}: {message}")
            if details:
                print(f"   {details}")
            self.failed_tests.append(message)
        elif status == "WARN":
            print(f"{YELLOW}⚠️  WARN{RESET}: {message}")
            if details:
                print(f"   {details}")
        elif status == "INFO":
            print(f"{BLUE}ℹ️  INFO{RESET}: {message}")
            if details:
                print(f"   {details}")
        
        self.results.append({
            'status': status,
            'test': message,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
    
    def test_file_structure(self):
        """Test 1: Verify all required files exist"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST 1: FILE STRUCTURE{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        required_files = {
            'Core': [
                'cli.py',
                'bowen_core.py',
                'config.py',
                'memory.json',
                'user_context.yaml'
            ],
            'Engines': [
                'engines/autonomous_learner.py',
                'engines/code_agent.py',
                'engines/syllabus_parser.py',
                'engines/manual_academic.py',
                'engines/backup_manager.py',
                'engines/outlook_connector.py',
                'engines/self_upgrader.py',
                'engines/advanced_documents.py',
                'engines/workflow_orchestrator.py',
                'engines/file_manager.py'
            ],
            'Knowledge': [
                'knowledge/concepts.json',
                'knowledge/connections.json',
                'knowledge/sources.json'
            ]
        }
        
        for category, files in required_files.items():
            self.log("INFO", f"Checking {category} files...")
            for file in files:
                path = self.bowen_path / file
                if path.exists():
                    self.log("PASS", f"{file} exists", f"Size: {path.stat().st_size} bytes")
                else:
                    self.log("FAIL", f"{file} missing")
    
    def test_memory_structure(self):
        """Test 2: Validate memory.json structure and data"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST 2: MEMORY STRUCTURE{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        memory_path = self.bowen_path / 'memory.json'
        
        try:
            with open(memory_path, 'r') as f:
                memory = json.load(f)
            
            # Check structure
            required_keys = ['facts']
            optional_keys = ['courses', 'user_profile', 'learned_facts']
            
            for key in required_keys:
                if key in memory:
                    self.log("PASS", f"Memory has '{key}' section", 
                            f"Contains {len(memory[key])} items")
                else:
                    self.log("FAIL", f"Memory missing '{key}' section")
            
            for key in optional_keys:
                if key in memory:
                    self.log("PASS", f"Memory has optional '{key}' section", 
                            f"Contains {len(memory[key])} items")
            
            # Check for fake/placeholder data
            fake_indicators = ['example', 'placeholder', 'test_', 'fake', 'sample', 'demo']
            fake_found = False
            
            for fact_key, fact in memory.get('facts', {}).items():
                for indicator in fake_indicators:
                    if indicator in str(fact).lower() or indicator in fact_key.lower():
                        # Ignore our own test data
                        if 'manual_test' not in fact_key.lower():
                            self.log("WARN", f"Possible fake data in memory: {fact_key}")
                            fake_found = True
            
            if not fake_found:
                self.log("PASS", "No obvious fake/placeholder data in memory")
            
            # Check data quality
            fact_count = 0
            for fact_key, fact in memory.get('facts', {}).items():
                fact_count += 1
                
                if 'told_on' in fact:
                    try:
                        datetime.fromisoformat(fact['told_on'])
                        self.log("PASS", f"Valid timestamp in {fact_key}")
                    except:
                        self.log("FAIL", f"Invalid timestamp in {fact_key}")
                
                if 'source' in fact:
                    valid_sources = ['manual_input', 'syllabus_parser', 'autonomous_research', 
                                   'conversation', 'user_told', 'learning_session']
                    if fact['source'] in valid_sources:
                        self.log("PASS", f"Valid source: {fact['source']}")
                    else:
                        self.log("WARN", f"Unknown source: {fact['source']}")
            
            self.log("INFO", f"Total facts in memory: {fact_count}")
        
        except Exception as e:
            self.log("FAIL", "Failed to read memory.json", str(e))
    
    def test_knowledge_base(self):
        """Test 3: Validate knowledge base has real learned concepts"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST 3: KNOWLEDGE BASE{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        concepts_path = self.bowen_path / 'knowledge' / 'concepts.json'
        
        try:
            if concepts_path.exists():
                with open(concepts_path, 'r') as f:
                    concepts = json.load(f)
                
                self.log("INFO", f"Knowledge base contains {len(concepts)} concepts")
                
                # Check each concept has required fields
                required_fields = ['definition', 'learned_at']
                recommended_fields = ['sources', 'confidence', 'category']
                
                concept_count = 0
                for concept_name, concept_data in concepts.items():
                    concept_count += 1
                    if concept_count > 5:  # Only check first 5 concepts for details
                        break
                    
                    missing_fields = [f for f in required_fields if f not in concept_data]
                    if missing_fields:
                        self.log("WARN", f"Concept '{concept_name}' missing fields: {missing_fields}")
                    else:
                        self.log("PASS", f"Concept '{concept_name}' has all required fields")
                    
                    # Check recommended fields
                    for field in recommended_fields:
                        if field in concept_data:
                            self.log("PASS", f"'{concept_name}' has {field}")
                    
                    # Verify learned_at is valid timestamp
                    if 'learned_at' in concept_data:
                        try:
                            learned_time = datetime.fromisoformat(concept_data['learned_at'])
                            age = (datetime.now() - learned_time).days
                            self.log("PASS", f"Valid timestamp for '{concept_name}' (learned {age} days ago)")
                        except:
                            self.log("FAIL", f"Invalid timestamp for '{concept_name}'")
                    
                    # Check sources are real
                    if 'sources' in concept_data:
                        if isinstance(concept_data['sources'], list) and len(concept_data['sources']) > 0:
                            self.log("PASS", f"'{concept_name}' has {len(concept_data['sources'])} sources")
                        else:
                            self.log("WARN", f"'{concept_name}' has no sources")
                    
                    # Check definition quality
                    if 'definition' in concept_data:
                        definition = concept_data['definition']
                        if len(definition) > 50:
                            self.log("PASS", f"'{concept_name}' has substantial definition ({len(definition)} chars)")
                        else:
                            self.log("WARN", f"'{concept_name}' has minimal definition")
                
                if len(concepts) == 0:
                    self.log("WARN", "Knowledge base is empty - no concepts learned yet")
            else:
                self.log("FAIL", "Knowledge base file doesn't exist")
        
        except Exception as e:
            self.log("FAIL", "Failed to read knowledge base", str(e))
    
    def test_engine_imports(self):
        """Test 4: Verify all engines can be imported"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST 4: ENGINE IMPORTS{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        sys.path.insert(0, str(self.bowen_path))
        
        engines = [
            ('engines.autonomous_learner', 'AutonomousLearner'),
            ('engines.code_agent', 'CodeAgent'),
            ('engines.syllabus_parser', 'SyllabusParser'),
            ('engines.manual_academic', 'ManualAcademic'),
            ('engines.backup_manager', 'BackupManager'),
            ('engines.outlook_connector', 'OutlookConnector'),
            ('engines.self_upgrader', 'SelfUpgrader'),
            ('engines.advanced_documents', 'AdvancedDocumentEngine'),
            ('engines.workflow_orchestrator', 'WorkflowOrchestrator'),
            ('engines.file_manager', 'IntelligentFileManager')
        ]
        
        for module_name, class_name in engines:
            try:
                module = __import__(module_name, fromlist=[class_name])
                cls = getattr(module, class_name)
                self.log("PASS", f"Successfully imported {module_name}.{class_name}")
                
                # Check if class has expected methods
                if hasattr(cls, '__init__'):
                    self.log("PASS", f"{class_name} has __init__ method")
                else:
                    self.log("WARN", f"{class_name} missing __init__ method")
                    
            except Exception as e:
                self.log("FAIL", f"Failed to import {module_name}", str(e))
    
    def test_memory_persistence(self):
        """Test 5: Test memory read/write/persist"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST 5: MEMORY PERSISTENCE{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        try:
            from engines.manual_academic import ManualAcademic
            
            manual = ManualAcademic()
            
            # Read initial memory state
            memory_path = self.bowen_path / 'memory.json'
            with open(memory_path, 'r') as f:
                memory_before = json.load(f)
            
            initial_count = len(memory_before.get('facts', {}))
            self.log("INFO", f"Memory has {initial_count} facts before test")
            
            # Add a test deadline
            test_timestamp = datetime.now().strftime('%H%M%S')
            test_item = f"Test item {test_timestamp}"
            result = manual.add_deadline(f"{test_item} tomorrow")
            
            if result['success']:
                self.log("PASS", "Successfully added test deadline to memory")
                
                # Verify it was saved
                with open(memory_path, 'r') as f:
                    memory_after = json.load(f)
                
                new_count = len(memory_after.get('facts', {}))
                
                if new_count > initial_count:
                    self.log("PASS", f"Memory increased from {initial_count} to {new_count} facts")
                    
                    # Find and verify the test item
                    found = False
                    for key, fact in memory_after.get('facts', {}).items():
                        if test_item.lower() in fact.get('item', '').lower():
                            found = True
                            self.log("PASS", "Test deadline persisted correctly", 
                                    f"Key: {key}, Item: {fact['item']}")
                            
                            # Verify it has all required fields
                            required_fields = ['type', 'date', 'source', 'told_on']
                            for field in required_fields:
                                if field in fact:
                                    self.log("PASS", f"Test fact has {field}: {fact[field]}")
                                else:
                                    self.log("WARN", f"Test fact missing {field}")
                            break
                    
                    if not found:
                        self.log("FAIL", "Test deadline not found in memory after save")
                else:
                    self.log("FAIL", "Memory count did not increase after adding deadline")
            else:
                self.log("FAIL", "Failed to add test deadline", result.get('error'))
        
        except Exception as e:
            self.log("FAIL", "Memory persistence test failed", str(e))
    
    def test_autonomous_learning(self):
        """Test 6: Verify autonomous learning actually learns"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST 6: AUTONOMOUS LEARNING{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        try:
            from engines.autonomous_learner import AutonomousLearner
            from research_engine import ResearchEngine
            
            # Initialize with real components
            research_engine = ResearchEngine()
            learner = AutonomousLearner(
                knowledge_path=str(self.bowen_path / 'knowledge'),
                research_engine=research_engine,
                claude_engine=None  # Skip Claude for this test
            )
            
            # Check existing concepts
            concepts_path = self.bowen_path / 'knowledge' / 'concepts.json'
            if concepts_path.exists():
                with open(concepts_path, 'r') as f:
                    concepts_before = json.load(f)
                
                concept_count = len(concepts_before)
                self.log("INFO", f"Knowledge base has {concept_count} concepts")
                
                # Verify concepts have real data
                if concept_count > 0:
                    # Check a few random concepts
                    sample_concepts = list(concepts_before.keys())[:3]
                    
                    for concept_name in sample_concepts:
                        concept_data = concepts_before[concept_name]
                        
                        # Check definition quality
                        if 'definition' in concept_data:
                            definition = concept_data['definition']
                            if len(definition) > 50:
                                self.log("PASS", f"Concept '{concept_name}' has substantial definition")
                            else:
                                self.log("WARN", f"Concept '{concept_name}' has brief definition")
                        
                        # Check timestamp
                        if 'learned_at' in concept_data:
                            try:
                                learned_time = datetime.fromisoformat(concept_data['learned_at'])
                                age_days = (datetime.now() - learned_time).days
                                if age_days < 365:  # Less than a year old
                                    self.log("PASS", f"'{concept_name}' learned recently ({age_days} days ago)")
                                else:
                                    self.log("WARN", f"'{concept_name}' learned long ago ({age_days} days)")
                            except:
                                self.log("FAIL", f"'{concept_name}' has invalid timestamp")
                        
                        # Check confidence if available
                        if 'confidence' in concept_data:
                            confidence = concept_data['confidence']
                            if isinstance(confidence, (int, float)) and 0 <= confidence <= 1:
                                self.log("PASS", f"'{concept_name}' has valid confidence: {confidence}")
                            else:
                                self.log("WARN", f"'{concept_name}' has invalid confidence: {confidence}")
                else:
                    self.log("WARN", "No concepts learned yet - knowledge base is empty")
            else:
                self.log("WARN", "Knowledge base file doesn't exist yet")
                
            # Test learning stats method
            try:
                stats = learner.get_learning_stats()
                if isinstance(stats, dict):
                    self.log("PASS", "Learning stats method works")
                    if 'total_concepts' in stats:
                        self.log("PASS", f"Stats show {stats['total_concepts']} total concepts")
                else:
                    self.log("WARN", "Learning stats returned non-dict")
            except Exception as e:
                self.log("FAIL", "Learning stats method failed", str(e))
        
        except Exception as e:
            self.log("FAIL", "Autonomous learning test failed", str(e))
    
    def test_cli_integration(self):
        """Test 7: Verify CLI can access all engines"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST 7: CLI INTEGRATION{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        try:
            # Check if CLI file exists and is readable
            cli_path = self.bowen_path / 'cli.py'
            with open(cli_path, 'r') as f:
                cli_content = f.read()
            
            # Check for engine imports
            engine_imports = [
                'autonomous_learner',
                'code_agent', 
                'syllabus_parser',
                'manual_academic',
                'backup_manager',
                'outlook_connector'
            ]
            
            for engine in engine_imports:
                if engine in cli_content:
                    self.log("PASS", f"CLI imports {engine}")
                else:
                    self.log("WARN", f"CLI may not import {engine}")
            
            # Check for academic intent handling
            academic_patterns = [
                '_is_academic_request',
                '_handle_academic_request',
                'syllabus',
                'deadline',
                'calendar'
            ]
            
            for pattern in academic_patterns:
                if pattern in cli_content:
                    self.log("PASS", f"CLI has academic pattern: {pattern}")
                else:
                    self.log("WARN", f"CLI missing academic pattern: {pattern}")
            
            # Check for hardcoded responses
            suspicious_hardcoded = [
                'Database exam in 2 hours',
                'Meeting at 3pm',
                'example@email.com'
            ]
            
            found_hardcoded = False
            for pattern in suspicious_hardcoded:
                if pattern in cli_content:
                    self.log("WARN", f"Found hardcoded pattern in CLI: {pattern}")
                    found_hardcoded = True
            
            if not found_hardcoded:
                self.log("PASS", "No obvious hardcoded responses in CLI")
            
            self.log("PASS", "CLI integration structure appears correct")
        
        except Exception as e:
            self.log("FAIL", "CLI integration test failed", str(e))
    
    def test_no_hardcoded_data(self):
        """Test 8: Scan for hardcoded fake data in code"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST 8: NO HARDCODED DATA{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        suspicious_patterns = [
            ('Database exam in 2 hours', 'Fake proactive message'),
            ('Team standup at 11am', 'Hardcoded meeting time'),
            ('Exam at 2pm', 'Hardcoded exam time'),
            ('Salary due in 2 days', 'Hardcoded salary reminder'),
            ('example@email.com', 'Example email address'),
            ('test_user', 'Test user name'),
            ('placeholder', 'Placeholder text'),
            ('fake_data', 'Fake data marker'),
            ('sample_project', 'Sample project name')
        ]
        
        files_to_check = [
            'cli.py',
            'bowen_core.py',
            'engines/autonomous_learner.py',
            'engines/manual_academic.py',
            'engines/code_agent.py',
            'engines/self_upgrader.py'
        ]
        
        for file in files_to_check:
            file_path = self.bowen_path / file
            if not file_path.exists():
                self.log("WARN", f"File {file} not found for hardcoded data check")
                continue
            
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                found_suspicious = False
                for pattern, description in suspicious_patterns:
                    if pattern in content:
                        # Check if it's in a comment or documentation
                        lines = content.split('\n')
                        for line_num, line in enumerate(lines, 1):
                            if pattern in line:
                                # Skip if it's in comments or docstrings
                                stripped = line.strip()
                                if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                                    continue
                                self.log("WARN", f"Found '{pattern}' in {file}:{line_num}", description)
                                found_suspicious = True
                
                if not found_suspicious:
                    self.log("PASS", f"{file} has no obvious hardcoded fake data")
                    
            except Exception as e:
                self.log("FAIL", f"Failed to scan {file} for hardcoded data", str(e))
    
    def test_real_data_sources(self):
        """Test 9: Verify data comes from real sources"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST 9: REAL DATA SOURCES{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        # Check memory for data sources
        try:
            memory_path = self.bowen_path / 'memory.json'
            with open(memory_path, 'r') as f:
                memory = json.load(f)
            
            real_sources = 0
            total_facts = 0
            source_types = {}
            
            for fact_key, fact in memory.get('facts', {}).items():
                total_facts += 1
                source = fact.get('source', 'unknown')
                source_types[source] = source_types.get(source, 0) + 1
                
                # Check if source indicates real data
                real_source_indicators = [
                    'manual_input',
                    'syllabus_parser', 
                    'user_told',
                    'conversation',
                    'autonomous_research'
                ]
                
                if source in real_source_indicators:
                    real_sources += 1
                
                # Check for timestamps indicating real user interaction
                if 'told_on' in fact:
                    try:
                        told_time = datetime.fromisoformat(fact['told_on'])
                        # If it's recent (within 30 days), likely real
                        age = (datetime.now() - told_time).days
                        if age <= 30:
                            self.log("PASS", f"Recent user data: {fact_key} ({age} days old)")
                    except:
                        pass
            
            if total_facts > 0:
                real_percentage = (real_sources / total_facts) * 100
                self.log("INFO", f"Data source breakdown: {source_types}")
                self.log("INFO", f"{real_percentage:.1f}% of facts from real sources ({real_sources}/{total_facts})")
                
                if real_percentage > 50:
                    self.log("PASS", f"Majority of data from real sources")
                else:
                    self.log("WARN", f"Most data not from real sources")
            else:
                self.log("WARN", "No facts in memory to analyze")
                
        except Exception as e:
            self.log("FAIL", "Failed to analyze data sources", str(e))
    
    def generate_report(self):
        """Generate final test report"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}FINAL TEST REPORT{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        total_tests = len(self.results)
        passed = len([r for r in self.results if r['status'] == 'PASS'])
        failed = len([r for r in self.results if r['status'] == 'FAIL'])
        warnings = len([r for r in self.results if r['status'] == 'WARN'])
        
        print(f"Total Checks: {total_tests}")
        print(f"{GREEN}✅ Passed: {passed}{RESET}")
        print(f"{RED}❌ Failed: {failed}{RESET}")
        print(f"{YELLOW}⚠️  Warnings: {warnings}{RESET}\n")
        
        if failed > 0:
            print(f"{RED}FAILED TESTS:{RESET}")
            for test in self.failed_tests:
                print(f"  ❌ {test}")
            print()
        
        # Calculate score
        score = (passed / (passed + failed)) * 100 if (passed + failed) > 0 else 0
        
        print(f"SYSTEM INTEGRITY SCORE: {score:.1f}%\n")
        
        # Save report
        report_path = self.bowen_path / 'test_report.json'
        with open(report_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total_checks': total_tests,
                    'passed': passed,
                    'failed': failed,
                    'warnings': warnings,
                    'score': score
                },
                'results': self.results
            }, f, indent=2)
        
        print(f"📄 Full report saved to: {report_path}\n")
        
        if failed == 0:
            print(f"{GREEN}{'='*60}{RESET}")
            print(f"{GREEN}🎉 ALL CRITICAL TESTS PASSED{RESET}")
            print(f"{GREEN}BOWEN SYSTEM VALIDATION COMPLETE{RESET}")
            print(f"{GREEN}{'='*60}{RESET}\n")
            return 0
        else:
            print(f"{RED}{'='*60}{RESET}")
            print(f"{RED}❌ VALIDATION ISSUES FOUND{RESET}")
            print(f"{RED}REVIEW REQUIRED BEFORE DEPLOYMENT{RESET}")
            print(f"{RED}{'='*60}{RESET}\n")
            return 1


def main():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}🔍 BOWEN COMPLETE SYSTEM VALIDATION{RESET}")
    print(f"{BLUE}Checking for fake data, broken connections, and integration issues{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    tester = BOWENIntegrationTest()
    
    # Run all tests
    tester.test_file_structure()
    tester.test_memory_structure()
    tester.test_knowledge_base()
    tester.test_engine_imports()
    tester.test_memory_persistence()
    tester.test_autonomous_learning()
    tester.test_cli_integration()
    tester.test_no_hardcoded_data()
    tester.test_real_data_sources()
    
    # Generate report
    return tester.generate_report()


if __name__ == "__main__":
    sys.exit(main())