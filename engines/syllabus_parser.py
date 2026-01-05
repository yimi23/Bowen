#!/usr/bin/env python3
"""
BOWEN Syllabus Parser
Extracts deadlines from academic syllabus PDFs with confidence scoring
"""

import fitz  # PyMuPDF
import re
from dateparser import parse
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class SyllabusParser:
    """Extract deadlines from syllabus PDFs with confidence scoring"""
    
    def __init__(self, memory_path='/Users/yimi/Desktop/bowen/memory.json'):
        self.memory_path = memory_path
        self.confidence_threshold = 0.8
        
        self.date_patterns = [
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:st|nd|rd|th)?,? \d{4}\b',
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
            r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),? (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}\b'
        ]
        
        self.deadline_keywords = [
            'exam', 'quiz', 'test', 'midterm', 'final',
            'assignment', 'homework', 'project', 'paper',
            'essay', 'presentation', 'due', 'submit', 'deadline'
        ]
    
    def parse_pdf(self, pdf_path):
        """Extract all course info and deadlines from PDF"""
        try:
            doc = fitz.open(pdf_path)
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            doc.close()
            
            course_info = self._extract_course_info(full_text)
            deadlines = self._extract_deadlines(full_text)
            office_hours = self._extract_office_hours(full_text)
            
            logger.info(f"Parsed syllabus: {course_info['name']}, found {len(deadlines)} deadlines")
            
            return {
                'course': course_info,
                'deadlines': deadlines,
                'office_hours': office_hours,
                'parsed_at': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Syllabus parsing failed: {e}")
            raise
    
    def _extract_course_info(self, text):
        """Extract course code, name, professor"""
        course_pattern = r'([A-Z]{2,4}\s*\d{3,4})[:\s-]+([^\n]+)'
        prof_pattern = r'(?:Professor|Instructor|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        
        course_match = re.search(course_pattern, text)
        prof_match = re.search(prof_pattern, text)
        
        return {
            'code': course_match.group(1).strip() if course_match else 'Unknown',
            'name': course_match.group(2).strip() if course_match else 'Unknown Course',
            'professor': prof_match.group(1) if prof_match else 'Unknown'
        }
    
    def _extract_deadlines(self, text):
        """Extract dates with context and confidence scores"""
        deadlines = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in self.deadline_keywords):
                context_lines = lines[max(0, i-1):min(i+3, len(lines))]
                context = ' '.join(context_lines)
                
                for pattern in self.date_patterns:
                    matches = re.findall(pattern, context, re.IGNORECASE)
                    for match in matches:
                        parsed_date = parse(match, settings={
                            'PREFER_DATES_FROM': 'future',
                            'RELATIVE_BASE': datetime(2026, 1, 5)  # Current date
                        })
                        
                        if parsed_date:
                            item = self._extract_item_name(context)
                            confidence = self._calculate_confidence(context, match)
                            
                            deadlines.append({
                                'item': item,
                                'date': parsed_date.strftime('%Y-%m-%d'),
                                'time': parsed_date.strftime('%H:%M') if parsed_date.hour != 0 else None,
                                'confidence': confidence,
                                'context': context[:150],
                                'source_line': i
                            })
        
        # Remove duplicates, keep highest confidence
        unique = {}
        for d in deadlines:
            key = (d['item'], d['date'])
            if key not in unique or d['confidence'] > unique[key]['confidence']:
                unique[key] = d
        
        return sorted(unique.values(), key=lambda x: x['date'])
    
    def _extract_item_name(self, context):
        """Determine what the deadline is for"""
        patterns = [
            (r'(Exam \d+|Midterm Exam|Final Exam|Quiz \d+)', 'Exam'),
            (r'(Assignment \d+|Homework \d+|HW \d+)', 'Assignment'),
            (r'(Project \d+|Term Project)', 'Project'),
            (r'(Essay|Paper|Report)', 'Paper'),
            (r'(Presentation)', 'Presentation')
        ]
        
        for pattern, default in patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                return match.group(1).title()
        
        return 'Assignment'
    
    def _calculate_confidence(self, context, date_match):
        """Score confidence in extraction (0.0-1.0)"""
        score = 0.5
        
        # Boost for explicit deadline words
        if any(word in context.lower() for word in ['due', 'submit', 'deadline']):
            score += 0.3
        
        # Boost for clear date formats
        if re.match(r'\d{1,2}/\d{1,2}/\d{4}', date_match):
            score += 0.2
        
        # Boost if date and deadline word are close
        words = context.lower().split()
        date_words = date_match.lower().split()
        for dw in date_words:
            if dw in words:
                idx = words.index(dw)
                nearby = words[max(0, idx-3):min(len(words), idx+4)]
                if any(kw in nearby for kw in self.deadline_keywords):
                    score += 0.1
        
        return min(score, 1.0)
    
    def _extract_office_hours(self, text):
        """Extract office hours"""
        oh_pattern = r'(?:Office Hours?|OH):?\s*([^\n]{10,100})'
        match = re.search(oh_pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else 'Not specified'
    
    def save_to_memory(self, parsed_data):
        """Save to BOWEN's existing memory structure"""
        try:
            with open(self.memory_path, 'r') as f:
                memory = json.load(f)
        except:
            memory = {'facts': {}, 'courses': {}}
        
        # Add course
        course_code = parsed_data['course']['code']
        if 'courses' not in memory:
            memory['courses'] = {}
        
        memory['courses'][course_code] = {
            'name': parsed_data['course']['name'],
            'professor': parsed_data['course']['professor'],
            'office_hours': parsed_data['office_hours'],
            'syllabus_parsed_at': parsed_data['parsed_at']
        }
        
        # Add high-confidence deadlines as facts
        saved_count = 0
        for deadline in parsed_data['deadlines']:
            if deadline['confidence'] >= self.confidence_threshold:
                fact_key = f"{course_code}_{deadline['item'].replace(' ', '_')}_{deadline['date']}"
                
                memory['facts'][fact_key] = {
                    'type': 'deadline',
                    'course': course_code,
                    'course_name': parsed_data['course']['name'],
                    'item': deadline['item'],
                    'date': deadline['date'],
                    'time': deadline['time'],
                    'expires': f"{deadline['date']}T23:59:59",
                    'confidence': deadline['confidence'],
                    'source': 'syllabus_parser',
                    'told_on': datetime.now().isoformat()
                }
                saved_count += 1
        
        with open(self.memory_path, 'w') as f:
            json.dump(memory, f, indent=2)
        
        logger.info(f"Saved {saved_count} deadlines to memory for {course_code}")
        return saved_count


# CLI test
if __name__ == "__main__":
    import sys
    
    parser = SyllabusParser()
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        print(f"\n📄 Parsing {pdf_path}...\n")
        
        result = parser.parse_pdf(pdf_path)
        
        print(f"Course: {result['course']['code']} - {result['course']['name']}")
        print(f"Professor: {result['course']['professor']}")
        print(f"Office Hours: {result['office_hours']}\n")
        print(f"Found {len(result['deadlines'])} deadlines:\n")
        
        for d in result['deadlines']:
            conf = "✅" if d['confidence'] >= 0.8 else "⚠️"
            time_str = f" at {d['time']}" if d['time'] else ""
            print(f"{conf} {d['date']}{time_str}: {d['item']} (confidence: {d['confidence']:.2f})")
        
        saved = parser.save_to_memory(result)
        print(f"\n✅ Saved {saved} high-confidence deadlines to memory")
    else:
        print("Usage: python syllabus_parser.py <path_to_syllabus.pdf>")