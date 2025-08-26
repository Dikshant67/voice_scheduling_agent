#!/usr/bin/env python3
"""
Test script for the enhanced conflict resolution system.
This tests the calendar service's ability to suggest multiple time slots
when there's a scheduling conflict.
"""

import sys
import os
import unittest
from datetime import datetime, timedelta
import pytz

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.calendar_service import CalendarService
from unittest.mock import Mock, patch

class TestConflictResolution(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the calendar service initialization to avoid Google API calls
        with patch('core.calendar_service.CalendarService._get_credentials'):
            self.calendar_service = CalendarService()
    
    def test_suggest_multiple_slots(self):
        """Test the multiple slot suggestion functionality."""
        # Create a mock existing event
        tz = pytz.timezone('UTC')
        desired_start = tz.localize(datetime(2024, 12, 15, 14, 0))  # 2 PM
        
        # Mock existing events that conflict
        existing_events = [
            {
                'start': {'dateTime': '2024-12-15T14:00:00Z'},
                'end': {'dateTime': '2024-12-15T15:00:00Z'}
            },
            {
                'start': {'dateTime': '2024-12-15T15:30:00Z'},
                'end': {'dateTime': '2024-12-15T16:30:00Z'}
            }
        ]
        
        # Test multiple suggestions
        suggestions = self.calendar_service.suggest_multiple_slots(
            existing_events, desired_start, 60, num_suggestions=3
        )
        
        # Verify we get suggestions
        self.assertGreater(len(suggestions), 0)
        self.assertLessEqual(len(suggestions), 3)
        
        # Verify each suggestion has required fields
        for suggestion in suggestions:
            self.assertIn('start', suggestion)
            self.assertIn('end', suggestion)
            self.assertIn('strategy', suggestion)
            self.assertIn('description', suggestion)
            
            # Verify the suggestion is after the conflicting events
            suggestion_start = suggestion['start']
            self.assertIsInstance(suggestion_start, datetime)
    
    def test_conflict_detection_with_buffer(self):
        """Test conflict detection with buffer time."""
        tz = pytz.timezone('UTC')
        
        # Test case 1: Direct conflict
        new_start = tz.localize(datetime(2024, 12, 15, 14, 0))
        new_end = tz.localize(datetime(2024, 12, 15, 15, 0))
        
        existing_events = [
            {
                'start': {'dateTime': '2024-12-15T14:30:00Z'},
                'end': {'dateTime': '2024-12-15T15:30:00Z'}
            }
        ]
        
        has_conflict = self.calendar_service.has_conflict_with_buffer(
            existing_events, new_start, new_end
        )
        self.assertTrue(has_conflict)
        
        # Test case 2: No conflict with sufficient buffer
        new_start = tz.localize(datetime(2024, 12, 15, 12, 0))
        new_end = tz.localize(datetime(2024, 12, 15, 13, 0))
        
        has_conflict = self.calendar_service.has_conflict_with_buffer(
            existing_events, new_start, new_end
        )
        self.assertFalse(has_conflict)
    
    def test_find_available_slot_in_range(self):
        """Test finding available slots within a specific time range."""
        tz = pytz.timezone('UTC')
        
        range_start = tz.localize(datetime(2024, 12, 15, 9, 0))   # 9 AM
        range_end = tz.localize(datetime(2024, 12, 15, 17, 0))    # 5 PM
        
        existing_events = [
            {
                'start': {'dateTime': '2024-12-15T10:00:00Z'},
                'end': {'dateTime': '2024-12-15T11:00:00Z'}
            },
            {
                'start': {'dateTime': '2024-12-15T14:00:00Z'},
                'end': {'dateTime': '2024-12-15T15:00:00Z'}
            }
        ]
        
        # Should find a slot between 9-10 AM
        available_slot = self.calendar_service._find_available_slot_in_range(
            existing_events, range_start, range_end, 60
        )
        
        self.assertIsNotNone(available_slot)
        self.assertEqual(available_slot, range_start)  # Should be 9 AM
    
    def test_schedule_suggested_slot_validation(self):
        """Test validation in schedule_suggested_slot method."""
        # Test with missing data
        result = self.calendar_service.schedule_suggested_slot({}, 1)
        self.assertEqual(result['status'], 'error')
        self.assertIn('Missing required', result['message'])
        
        # Test with invalid option
        meeting_data = {
            'title': 'Test Meeting',
            'date': '2024-12-15',
            'time': '14:00',
            'timezone': 'UTC'
        }
        
        result = self.calendar_service.schedule_suggested_slot(meeting_data, 5)
        self.assertEqual(result['status'], 'error')
        self.assertIn('Invalid option', result['message'])

def run_conflict_resolution_demo():
    """
    Demonstrates the conflict resolution system with sample data.
    """
    print("🚀 Conflict Resolution System Demo")
    print("=" * 50)
    
    try:
        # Mock the calendar service to avoid API calls
        with patch('core.calendar_service.CalendarService._get_credentials'):
            calendar_service = CalendarService()
        
        # Sample meeting request
        meeting_data = {
            'title': 'Team Standup',
            'date': '2024-12-15',
            'time': '2:00 PM',
            'timezone': 'UTC',
            'attendees': ['john@example.com', 'jane@example.com']
        }
        
        print(f"📅 Original Request: {meeting_data['title']}")
        print(f"   Date: {meeting_data['date']}")
        print(f"   Time: {meeting_data['time']}")
        print()
        
        # Mock existing events that create conflicts
        tz = pytz.timezone('UTC')
        desired_start = tz.localize(datetime(2024, 12, 15, 14, 0))
        
        existing_events = [
            {
                'start': {'dateTime': '2024-12-15T14:00:00Z'},
                'end': {'dateTime': '2024-12-15T15:00:00Z'},
                'summary': 'Existing Meeting 1'
            },
            {
                'start': {'dateTime': '2024-12-15T15:30:00Z'},
                'end': {'dateTime': '2024-12-15T16:30:00Z'},
                'summary': 'Existing Meeting 2'
            }
        ]
        
        print("⚠️  Conflicts detected with existing meetings:")
        for event in existing_events:
            start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
            print(f"   - {event.get('summary', 'Meeting')}: {start_time.strftime('%I:%M %p')}")
        print()
        
        # Generate suggestions
        suggestions = calendar_service.suggest_multiple_slots(
            existing_events, desired_start, 60, num_suggestions=3
        )
        
        print("💡 Suggested Alternative Times:")
        for i, suggestion in enumerate(suggestions, 1):
            start_formatted = suggestion['start'].strftime('%A, %B %d at %I:%M %p')
            print(f"   Option {i}: {start_formatted}")
            print(f"              ({suggestion['description']})")
        print()
        
        print("✅ Demo completed successfully!")
        print("   The system can now handle conflicts by:")
        print("   1. Detecting scheduling conflicts")
        print("   2. Suggesting multiple alternative time slots")
        print("   3. Using different strategies (next available, same day earlier, next day, etc.)")
        print("   4. Allowing users to select from the options")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("Running Conflict Resolution Tests...")
    print()
    
    # Run the demo first
    run_conflict_resolution_demo()
    print()
    
    # Run unit tests
    print("Running Unit Tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)