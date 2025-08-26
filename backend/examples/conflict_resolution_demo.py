#!/usr/bin/env python3
"""
Interactive demo of the conflict resolution system.
This simulates the complete user experience without requiring actual voice input.
"""

import sys
import os
from datetime import datetime, timedelta
import pytz

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def simulate_conflict_resolution():
    """
    Simulates the complete conflict resolution flow.
    """
    print("🎤 Voice Scheduling Agent - Conflict Resolution Demo")
    print("=" * 60)
    print()
    
    # Simulate user's initial request
    print("👤 User: \"Schedule a team standup for tomorrow at 2 PM\"")
    print()
    
    # Simulate system processing
    print("🤖 System: Processing your request...")
    print("   ✓ Extracted meeting details:")
    print("     - Title: Team Standup")
    print("     - Date: Tomorrow")
    print("     - Time: 2:00 PM")
    print("   ✓ Checking calendar for conflicts...")
    print()
    
    # Simulate conflict detection
    print("⚠️  System: Conflict detected!")
    print("   Existing meetings found:")
    print("   - Daily Sync: 2:00 PM - 2:30 PM")
    print("   - Client Call: 3:00 PM - 4:00 PM")
    print()
    
    # Simulate multiple suggestions
    print("🤖 System: \"I found a conflict with your requested time of")
    print("   Tuesday, December 17 at 02:00 PM. Here are some alternative options:")
    print()
    print("   Option 1: Tuesday, December 17 at 04:15 PM")
    print("            (Next available time slot)")
    print()
    print("   Option 2: Tuesday, December 17 at 10:00 AM") 
    print("            (Earlier the same day)")
    print()
    print("   Option 3: Wednesday, December 18 at 02:00 PM")
    print("            (Same time tomorrow)")
    print()
    print("   Which option would you prefer? You can say 'option 1',")
    print("   'option 2', 'option 3', or ask me to suggest different times.\"")
    print()
    
    # Simulate user selection
    print("👤 User: \"Option 2 sounds good\"")
    print()
    
    # Simulate system processing selection
    print("🤖 System: Processing your selection...")
    print("   ✓ Recognized selection: Option 2")
    print("   ✓ Validating time slot availability...")
    print("   ✓ Creating calendar event...")
    print()
    
    # Simulate confirmation
    print("🤖 System: \"Excellent! I've scheduled 'Team Standup' for")
    print("   Tuesday, December 17 at 10:00 AM (Option 2 - Earlier the same day).\"")
    print()
    
    # Show final result
    print("✅ Meeting Successfully Scheduled!")
    print("   📅 Title: Team Standup")
    print("   📅 Date: Tuesday, December 17, 2024")
    print("   📅 Time: 10:00 AM - 11:00 AM")
    print("   📅 Strategy: Earlier the same day")
    print()
    
    print("🎯 Key Benefits Demonstrated:")
    print("   ✓ Automatic conflict detection")
    print("   ✓ Multiple intelligent suggestions")
    print("   ✓ Natural language selection")
    print("   ✓ Clear confirmation with details")
    print("   ✓ User-friendly descriptions")

def demonstrate_different_scenarios():
    """
    Shows different conflict resolution scenarios.
    """
    print("\n" + "=" * 60)
    print("📋 Additional Scenarios")
    print("=" * 60)
    
    scenarios = [
        {
            "user_input": "Book the conference room for Friday at 9 AM",
            "conflict": "All-hands meeting: 9:00 AM - 10:00 AM",
            "suggestions": [
                "Option 1: Friday at 10:15 AM (Next available)",
                "Option 2: Friday at 8:00 AM (Earlier same day)", 
                "Option 3: Monday at 9:00 AM (Next week same time)"
            ],
            "user_choice": "The first option",
            "result": "Conference room booked for Friday at 10:15 AM"
        },
        {
            "user_input": "Schedule client presentation for today at 3 PM",
            "conflict": "Team meeting: 3:00 PM - 4:00 PM",
            "suggestions": [
                "Option 1: Today at 4:15 PM (Next available)",
                "Option 2: Today at 1:00 PM (Earlier same day)",
                "Option 3: Tomorrow at 3:00 PM (Same time tomorrow)"
            ],
            "user_choice": "I want different times",
            "result": "System asks for specific preferred time"
        },
        {
            "user_input": "Set up lunch meeting for Wednesday at noon",
            "conflict": "Department lunch: 12:00 PM - 1:00 PM",
            "suggestions": [
                "Option 1: Wednesday at 1:15 PM (Next available)",
                "Option 2: Wednesday at 11:00 AM (Earlier same day)",
                "Option 3: Thursday at 12:00 PM (Same time next day)"
            ],
            "user_choice": "Three",
            "result": "Lunch meeting scheduled for Thursday at 12:00 PM"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n🎬 Scenario {i}:")
        print(f"👤 User: \"{scenario['user_input']}\"")
        print(f"⚠️  Conflict: {scenario['conflict']}")
        print("🤖 Suggestions:")
        for suggestion in scenario['suggestions']:
            print(f"   {suggestion}")
        print(f"👤 User: \"{scenario['user_choice']}\"")
        print(f"✅ Result: {scenario['result']}")

def show_technical_details():
    """
    Shows the technical implementation details.
    """
    print("\n" + "=" * 60)
    print("🔧 Technical Implementation")
    print("=" * 60)
    
    print("\n📊 Suggestion Strategies:")
    strategies = [
        ("next_available", "Finds the next free slot after requested time"),
        ("earlier_same_day", "Looks for slots earlier in the day (from 9 AM)"),
        ("next_day_same_time", "Suggests same time on following day"),
        ("common_time", "Suggests popular meeting times (10 AM, 2 PM, 4 PM)")
    ]
    
    for strategy, description in strategies:
        print(f"   • {strategy}: {description}")
    
    print("\n🎯 Selection Processing:")
    patterns = [
        "option\\s*(\\d+)",
        "choice\\s*(\\d+)", 
        "number\\s*(\\d+)",
        "^(\\d+)$",
        "first|one|1st → 1",
        "second|two|2nd → 2",
        "third|three|3rd → 3"
    ]
    
    for pattern in patterns:
        print(f"   • {pattern}")
    
    print("\n⚙️ Configuration:")
    config = [
        ("BUFFER_MINUTES", "15", "Minutes between meetings"),
        ("DEFAULT_MEETING_DURATION", "60", "Default meeting length"),
        ("num_suggestions", "3", "Number of alternatives to suggest"),
        ("working_hours_start", "9", "Start of working day (9 AM)")
    ]
    
    for setting, value, description in config:
        print(f"   • {setting}: {value} - {description}")

if __name__ == '__main__':
    # Run the main demo
    simulate_conflict_resolution()
    
    # Show additional scenarios
    demonstrate_different_scenarios()
    
    # Show technical details
    show_technical_details()
    
    print("\n" + "=" * 60)
    print("🚀 Demo Complete!")
    print("=" * 60)
    print("\nThe enhanced conflict resolution system provides:")
    print("✓ Intelligent conflict detection")
    print("✓ Multiple suggestion strategies") 
    print("✓ Natural language processing")
    print("✓ Flexible user interaction")
    print("✓ Comprehensive error handling")
    print("\nReady for production use! 🎉")