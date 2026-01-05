#!/usr/bin/env python3
"""
Real-Time Context Engine
Always knows: current date, time, location
NO hardcoded dates EVER
"""

from datetime import datetime
import pytz
import requests
import json
from pathlib import Path

class RealTimeContext:
    def __init__(self):
        self.user_location = "Mount Pleasant, Michigan, US"
        self.timezone = "America/Detroit"
        self.cache_file = Path('/Users/yimi/Desktop/bowen/realtime_cache.json')
    
    def get_current_datetime(self):
        """Get ACTUAL current date and time"""
        tz = pytz.timezone(self.timezone)
        now = datetime.now(tz)
        
        return {
            'datetime': now.isoformat(),
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H:%M:%S'),
            'day_of_week': now.strftime('%A'),
            'month': now.strftime('%B'),
            'day': now.day,
            'year': now.year,
            'timezone': self.timezone,
            'formatted': now.strftime('%A, %B %d, %Y at %I:%M %p')
        }
    
    def get_location(self):
        """Get user's current location"""
        return {
            'city': 'Mount Pleasant',
            'state': 'Michigan',
            'country': 'US',
            'timezone': self.timezone,
            'formatted': self.user_location
        }
    
    def calculate_age(self, birthday: str):
        """Calculate REAL age based on TODAY'S date"""
        tz = pytz.timezone(self.timezone)
        now = datetime.now(tz)
        birth_date = datetime.strptime(birthday, '%Y-%m-%d').replace(tzinfo=tz)
        
        age = now.year - birth_date.year
        
        # Adjust if birthday hasn't happened yet this year
        if now.month < birth_date.month or (now.month == birth_date.month and now.day < birth_date.day):
            age -= 1
        
        # Days until next birthday
        next_birthday = datetime(now.year, birth_date.month, birth_date.day).replace(tzinfo=tz)
        if next_birthday < now:
            next_birthday = datetime(now.year + 1, birth_date.month, birth_date.day).replace(tzinfo=tz)
        
        days_until = (next_birthday - now).days
        
        return {
            'current_age': age,
            'next_age': age + 1,
            'days_until_birthday': days_until,
            'birthday_this_year': next_birthday.strftime('%Y-%m-%d')
        }
    
    def get_full_context(self):
        """Get complete real-time context"""
        dt = self.get_current_datetime()
        loc = self.get_location()
        age_info = self.calculate_age('2003-01-16')  # Praise's birthday
        
        context = {
            'timestamp': datetime.now().isoformat(),
            'current_date': dt['date'],
            'current_time': dt['time'],
            'day_of_week': dt['day_of_week'],
            'formatted_datetime': dt['formatted'],
            'location': loc['formatted'],
            'timezone': self.timezone,
            'user': {
                'age': age_info['current_age'],
                'birthday_coming': f"in {age_info['days_until_birthday']} days" if age_info['days_until_birthday'] > 0 else "TODAY!",
                'turning': age_info['next_age']
            }
        }
        
        # Cache for quick access
        with open(self.cache_file, 'w') as f:
            json.dump(context, f, indent=2)
        
        return context
    
    def format_for_prompt(self):
        """Format context for Claude system prompt"""
        ctx = self.get_full_context()
        
        return f"""
REAL-TIME CONTEXT (ALWAYS USE THIS):

Current Date: {ctx['formatted_datetime']}
Location: {ctx['location']} ({ctx['timezone']})
User Age: {ctx['user']['age']} (turning {ctx['user']['turning']} {ctx['user']['birthday_coming']})

CRITICAL: Always use these REAL values. Never hardcode dates or times.
"""


# Test
if __name__ == "__main__":
    rt = RealTimeContext()
    context = rt.get_full_context()
    
    print("\n📍 REAL-TIME CONTEXT\n")
    print(f"Right now: {context['formatted_datetime']}")
    print(f"Location: {context['location']}")
    print(f"Age: {context['user']['age']} (turning {context['user']['turning']} {context['user']['birthday_coming']})")
    print("\nFormatted for prompt:")
    print(rt.format_for_prompt())