#!/usr/bin/env python3
"""
Find ALL fake/theatrical responses in BOWEN codebase
"""

import os
import re
from pathlib import Path

BOWEN_PATH = Path('/Users/yimi/Desktop/bowen')

# Patterns that indicate fake actions
FAKE_PATTERNS = {
    'THEATRICAL_ACTIONS': [
        r'\*[^*]+\*',  # *does something*
        r'beep',
        r'whir',
        r'activating',
        r'performing',
        r'executing.*check'
    ],
    'FAKE_CLAIMS': [
        r'I (?:have|will) (?:captured|taken|recorded|saved)',
        r'screenshot (?:captured|taken|saved)',
        r'alarm (?:played|activated)',
        r'I am (?:capturing|taking|recording)',
        r'discreetly',
        r'Mr\. Oyimi'
    ],
    'HARDCODED_DATA': [
        r'exam (?:in|at) \d+(?:pm|am)',
        r'Database exam',
        r'standup at \d+',
        r'salary due',
        r'Team meeting'
    ]
}

def scan_file(filepath):
    """Scan a file for fake patterns"""
    problems = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        for category, patterns in FAKE_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Find line number
                    line_num = content[:match.start()].count('\n') + 1
                    line_content = lines[line_num - 1].strip()
                    
                    problems.append({
                        'file': str(filepath.relative_to(BOWEN_PATH)),
                        'line': line_num,
                        'category': category,
                        'pattern': pattern,
                        'content': line_content[:100]
                    })
    except Exception as e:
        pass
    
    return problems

def main():
    print("\n" + "="*60)
    print("🔍 AUDITING BOWEN FOR FAKE/THEATRICAL RESPONSES")
    print("="*60 + "\n")
    
    files_to_check = []
    for ext in ['*.py']:
        files_to_check.extend(BOWEN_PATH.rglob(ext))
    
    all_problems = []
    for filepath in files_to_check:
        if 'bowen_env' in str(filepath):
            continue
        problems = scan_file(filepath)
        all_problems.extend(problems)
    
    if not all_problems:
        print("✅ No obvious fake patterns found\n")
        return
    
    # Group by category
    by_category = {}
    for prob in all_problems:
        cat = prob['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(prob)
    
    for category, problems in by_category.items():
        print(f"\n🚨 {category}: {len(problems)} issues found\n")
        
        for prob in problems[:10]:  # Show first 10
            print(f"  {prob['file']}:{prob['line']}")
            print(f"    → {prob['content']}")
            print()
    
    print("="*60)
    print(f"TOTAL ISSUES FOUND: {len(all_problems)}")
    print("="*60 + "\n")
    
    # Save detailed report
    import json
    with open(BOWEN_PATH / 'fake_audit_report.json', 'w') as f:
        json.dump(all_problems, f, indent=2)
    
    print("Full report saved to: fake_audit_report.json\n")

if __name__ == "__main__":
    main()