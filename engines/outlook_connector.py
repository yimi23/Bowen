#!/usr/bin/env python3
"""
BOWEN Outlook Connector
Microsoft Graph API integration for calendar and email
"""

from msal import PublicClientApplication
import requests
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class OutlookConnector:
    def __init__(self):
        # Microsoft's public client ID (Graph Explorer)
        self.client_id = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
        self.authority = "https://login.microsoftonline.com/common"
        self.scopes = [
            "https://graph.microsoft.com/Calendars.Read",
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/User.Read"
        ]
        self.token_cache_file = "/Users/yimi/Desktop/bowen/outlook_token.json"
        self.app = PublicClientApplication(
            self.client_id,
            authority=self.authority
        )
        self._token = None
        
        logger.info("Outlook connector initialized")
    
    def get_token(self):
        """Get access token via device code flow"""
        if self._token:
            return self._token
            
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(self.scopes, account=accounts[0])
            if result and 'access_token' in result:
                self._token = result['access_token']
                return self._token
        
        flow = self.app.initiate_device_flow(scopes=self.scopes)
        if "user_code" not in flow:
            raise ValueError("Failed to create device flow")
        
        print("\n" + "="*60)
        print("🔐 OUTLOOK LOGIN REQUIRED")
        print("="*60)
        print(flow["message"])
        print("="*60 + "\n")
        
        result = self.app.acquire_token_by_device_flow(flow)
        
        if "access_token" in result:
            self._token = result['access_token']
            print("✅ Authenticated successfully!\n")
            return self._token
        else:
            raise Exception(f"Authentication failed: {result.get('error_description')}")
    
    def get_calendar_events(self, days_ahead=7):
        """Get calendar events for next X days"""
        try:
            token = self.get_token()
            headers = {'Authorization': f'Bearer {token}'}
            
            # Get events from today onwards
            url = "https://graph.microsoft.com/v1.0/me/calendar/events"
            params = {
                '$select': 'subject,start,end,location,bodyPreview',
                '$top': 100,
                '$orderby': 'start/dateTime'
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                events = response.json().get('value', [])
                return self._format_events(events)
            else:
                raise Exception(f"Failed to get calendar: {response.text}")
        except Exception as e:
            logger.error(f"Error getting calendar events: {e}")
            raise
    
    def get_recent_emails(self, count=10):
        """Get recent emails"""
        try:
            token = self.get_token()
            headers = {'Authorization': f'Bearer {token}'}
            
            url = "https://graph.microsoft.com/v1.0/me/messages"
            params = {
                '$select': 'subject,from,receivedDateTime,bodyPreview,isRead',
                '$top': count,
                '$orderby': 'receivedDateTime DESC'
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                emails = response.json().get('value', [])
                return self._format_emails(emails)
            else:
                raise Exception(f"Failed to get emails: {response.text}")
        except Exception as e:
            logger.error(f"Error getting recent emails: {e}")
            raise
    
    def _format_events(self, events):
        """Format calendar events for BOWEN"""
        formatted = []
        for event in events:
            formatted.append({
                'title': event['subject'],
                'start': event['start']['dateTime'],
                'end': event['end']['dateTime'],
                'location': event.get('location', {}).get('displayName', 'No location'),
                'description': event.get('bodyPreview', '')
            })
        return formatted
    
    def _format_emails(self, emails):
        """Format emails for BOWEN"""
        formatted = []
        for email in emails:
            formatted.append({
                'subject': email['subject'],
                'from': email['from']['emailAddress']['address'],
                'received': email['receivedDateTime'],
                'preview': email['bodyPreview'],
                'read': email['isRead']
            })
        return formatted


# Test function
if __name__ == "__main__":
    connector = OutlookConnector()
    
    print("Testing Outlook connection...")
    
    try:
        # Test calendar
        print("\n📅 Fetching calendar events...")
        events = connector.get_calendar_events()
        print(f"Found {len(events)} events")
        for event in events[:3]:
            print(f"  - {event['title']} at {event['start']}")
        
        # Test email
        print("\n📧 Fetching recent emails...")
        emails = connector.get_recent_emails(5)
        print(f"Found {len(emails)} emails")
        for email in emails[:3]:
            print(f"  - From {email['from']}: {email['subject']}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("This is expected if you haven't authenticated yet.")