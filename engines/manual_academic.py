#!/usr/bin/env python3
"""
BOWEN Manual Academic Input
Quick input for deadlines and academic tasks via natural language
"""

from datetime import datetime
import json
from dateparser import parse
import logging

logger = logging.getLogger(__name__)

class ManualAcademic:
    """Quick manual input for deadlines/academic tasks"""
    
    def __init__(self, memory_path='/Users/yimi/Desktop/bowen/memory.json'):
        self.memory_path = memory_path
    
    def add_deadline(self, description, course=None):
        """
        Add deadline from natural language
        Examples:
        - "Database exam Friday"
        - "Essay due January 20"
        - "Midterm Feb 15 at 2pm"
        """
        try:
            with open(self.memory_path, 'r') as f:
                memory = json.load(f)
        except:
            memory = {'facts': {}}
        
        # Parse date - try multiple approaches
        parsed_date = None
        
        # First try parsing the full description
        parsed_date = parse(description, settings={'PREFER_DATES_FROM': 'future'})
        
        # If that fails, try extracting just the date part
        if not parsed_date:
            import re
            date_patterns = [
                r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:, \d{4})?\b',
                r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
                r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
                r'\b(?:today|tomorrow|next week)\b'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    date_str = match.group()
                    parsed_date = parse(date_str, settings={'PREFER_DATES_FROM': 'future'})
                    if parsed_date:
                        break
        
        # If still no date, try relative parsing
        if not parsed_date:
            # Try common relative formats
            relative_tests = [
                description.replace('exam', 'on').replace('due', 'on'),
                re.sub(r'^[^a-zA-Z]*([a-zA-Z\s]+)', r'\1', description)  # Remove leading words
            ]
            
            for test in relative_tests:
                parsed_date = parse(test, settings={'PREFER_DATES_FROM': 'future'})
                if parsed_date:
                    break
        
        if not parsed_date:
            return {"success": False, "error": "Couldn't parse date"}
        
        # Extract item name
        date_words = ['due', 'on', 'at', 'january', 'february', 'march', 'april',
                     'may', 'june', 'july', 'august', 'september', 'october',
                     'november', 'december', 'monday', 'tuesday', 'wednesday',
                     'thursday', 'friday', 'saturday', 'sunday', 'this', 'next']
        
        words = description.lower().split()
        item_words = []
        for word in words:
            if word in date_words:
                break
            item_words.append(word)
        
        item = ' '.join(item_words).strip() or 'Task'
        
        # Create fact
        fact_key = f"manual_{item.replace(' ', '_')}_{parsed_date.strftime('%Y%m%d%H%M')}"
        
        memory['facts'][fact_key] = {
            'type': 'deadline',
            'item': item.title(),
            'course': course or 'General',
            'date': parsed_date.strftime('%Y-%m-%d'),
            'time': parsed_date.strftime('%H:%M') if parsed_date.hour != 0 else None,
            'expires': parsed_date.strftime('%Y-%m-%dT23:59:59'),
            'source': 'manual_input',
            'confidence': 1.0,
            'told_on': datetime.now().isoformat()
        }
        
        with open(self.memory_path, 'w') as f:
            json.dump(memory, f, indent=2)
        
        logger.info(f"Added deadline: {item} on {parsed_date.strftime('%Y-%m-%d')}")
        
        return {
            "success": True,
            "item": item.title(),
            "date": parsed_date.strftime('%B %d, %Y'),
            "time": parsed_date.strftime('%I:%M %p') if parsed_date.hour != 0 else None
        }
    
    def get_upcoming_deadlines(self, days=7):
        """Get deadlines from memory within X days"""
        try:
            with open(self.memory_path, 'r') as f:
                memory = json.load(f)
        except:
            return []
        
        now = datetime.now()
        upcoming = []
        
        for key, fact in memory.get('facts', {}).items():
            if fact.get('type') == 'deadline':
                deadline_date = datetime.fromisoformat(fact['date'])
                days_until = (deadline_date - now).days
                
                if 0 <= days_until <= days:
                    upcoming.append({
                        'item': fact['item'],
                        'course': fact.get('course', 'Unknown'),
                        'date': fact['date'],
                        'time': fact.get('time'),
                        'days_until': days_until
                    })
        
        return sorted(upcoming, key=lambda x: x['date'])
    
    def list_all_deadlines(self):
        """Get all deadlines from memory"""
        try:
            with open(self.memory_path, 'r') as f:
                memory = json.load(f)
        except:
            return []
        
        deadlines = []
        for key, fact in memory.get('facts', {}).items():
            if fact.get('type') == 'deadline':
                deadlines.append({
                    'item': fact['item'],
                    'course': fact.get('course', 'Unknown'),
                    'date': fact['date'],
                    'time': fact.get('time'),
                    'source': fact.get('source', 'unknown')
                })
        
        return sorted(deadlines, key=lambda x: x['date'])
    
    def remove_deadline(self, item_name, date):
        """Remove a deadline from memory"""
        try:
            with open(self.memory_path, 'r') as f:
                memory = json.load(f)
        except:
            return {"success": False, "error": "No memory file found"}
        
        # Find and remove matching deadline
        removed = []
        facts_to_remove = []
        
        for key, fact in memory.get('facts', {}).items():
            if (fact.get('type') == 'deadline' and 
                fact.get('item', '').lower() == item_name.lower() and 
                fact.get('date') == date):
                facts_to_remove.append(key)
                removed.append(fact['item'])
        
        for key in facts_to_remove:
            del memory['facts'][key]
        
        if removed:
            with open(self.memory_path, 'w') as f:
                json.dump(memory, f, indent=2)
            
            logger.info(f"Removed {len(removed)} deadline(s)")
            return {"success": True, "removed": removed}
        else:
            return {"success": False, "error": "Deadline not found"}


# Test
if __name__ == "__main__":
    import sys
    
    manual = ManualAcademic()
    
    if len(sys.argv) > 1:
        description = ' '.join(sys.argv[1:])
        result = manual.add_deadline(description)
        
        if result['success']:
            time_str = f" at {result['time']}" if result['time'] else ""
            print(f"✅ Saved: {result['item']} on {result['date']}{time_str}")
        else:
            print(f"❌ {result['error']}")
    else:
        print("Usage: python manual_academic.py 'Database exam Friday at 2pm'")
        print("\nTesting upcoming deadlines...")
        deadlines = manual.get_upcoming_deadlines(14)
        if deadlines:
            print(f"Found {len(deadlines)} upcoming deadlines:")
            for d in deadlines:
                time_str = f" at {d['time']}" if d['time'] else ""
                print(f"  • {d['date']}{time_str}: {d['item']} ({d['course']})")
        else:
            print("No upcoming deadlines")