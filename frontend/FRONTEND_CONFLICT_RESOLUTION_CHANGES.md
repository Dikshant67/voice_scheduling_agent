# 🎨 Frontend Changes for Conflict Resolution

## Overview

The frontend has been enhanced to support the new conflict resolution system. Users can now see visual conflict notifications and interact with multiple scheduling options through both voice commands and UI buttons.

## 🔧 Changes Made

### 1. **New Interfaces Added**

```typescript
interface ConflictData {
  status: string;
  message: string;
  original_request: OriginalRequest;
  suggestions: ConflictSuggestion[];
  timezone: string;
}

interface OriginalRequest {
  start: string;
  end: string;
  start_formatted: string;
}

interface ConflictSuggestion {
  option: number;
  start: string;
  end: string;
  start_formatted: string;
  description: string;
  strategy: string;
}
```

### 2. **New State Variables**

```typescript
// Conflict resolution state
const [conflictData, setConflictData] = useState<ConflictData | null>(null);
const [isAwaitingConflictResolution, setIsAwaitingConflictResolution] =
  useState(false);
```

### 3. **Enhanced Message Handling**

Added support for new message types:

- `conflict_resolution` - Displays conflict options
- `meeting_scheduled` - Confirms successful scheduling
- `meeting_error` - Shows scheduling errors

```typescript
case "conflict_resolution":
  setIsProcessing(false);
  if (data.conflict_data) {
    setConflictData(data.conflict_data);
    setIsAwaitingConflictResolution(true);
    // Display conflict information
  }
  break;
```

### 4. **Configuration Sending**

Added automatic configuration sending to backend:

```typescript
const sendConfiguration = useCallback(() => {
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    const config = {
      type: "config",
      timezone: selectedTimezone,
      voice: selectedVoice,
      session_id: sessionId,
    };
    wsRef.current.send(JSON.stringify(config));
  }
}, [selectedTimezone, selectedVoice, sessionId]);
```

### 5. **Visual Conflict Resolution Panel**

Added a comprehensive UI panel that appears when conflicts are detected:

#### Features:

- **Original Request Display**: Shows the user's initial time request
- **Multiple Options**: Displays 3 alternative time slots with descriptions
- **Strategy Labels**: Shows which strategy was used (next available, earlier same day, etc.)
- **Interactive Buttons**: Click to select options or request different times
- **Voice Command Tips**: Reminds users they can speak their selection
- **Visual Feedback**: Orange/red gradient design to indicate conflicts

#### UI Components:

```jsx
{
  isAwaitingConflictResolution && conflictData && (
    <Card className="border-0 shadow-xl bg-gradient-to-r from-orange-50 to-red-50">
      <CardHeader>
        <CardTitle className="text-orange-800 flex items-center gap-2">
          <XCircle className="w-5 h-5" /> Scheduling Conflict Detected
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Original request display */}
        {/* Alternative options */}
        {/* Action buttons */}
      </CardContent>
    </Card>
  );
}
```

### 6. **Updated Voice Commands**

Extended the voice commands list to include conflict resolution options:

```typescript
const voiceCommands: VoiceCommand[] = [
  { command: "Schedule meeting", description: "Create a new meeting" },
  { command: "Cancel meeting", description: "Cancel existing meeting" },
  { command: "List meetings", description: "Show all meetings" },
  { command: "Set reminder", description: "Add meeting reminder" },
  // New conflict resolution commands
  { command: "Option 1", description: "Select first alternative time" },
  { command: "Option 2", description: "Select second alternative time" },
  { command: "Option 3", description: "Select third alternative time" },
  { command: "Different times", description: "Request different options" },
];
```

### 7. **Automatic Configuration Updates**

Added useEffect to send configuration when settings change:

```typescript
useEffect(() => {
  if (isConnected) {
    sendConfiguration();
  }
}, [selectedTimezone, selectedVoice, isConnected, sendConfiguration]);
```

## 🎮 User Experience Flow

### 1. **Normal Scheduling**

```
User: "Schedule meeting tomorrow at 2 PM"
↓
System: Processes request
↓
Success: Meeting scheduled confirmation
```

### 2. **Conflict Resolution**

```
User: "Schedule meeting tomorrow at 2 PM"
↓
System: Detects conflict
↓
UI: Shows conflict panel with 3 options
↓
User: Clicks "Select" or says "Option 2"
↓
System: Schedules selected option
↓
Success: Meeting scheduled with chosen time
```

## 🎨 Visual Design

### Color Scheme

- **Conflict Panel**: Orange/red gradient background
- **Options**: White cards with orange borders
- **Buttons**: Orange accent colors for conflict-related actions
- **Status**: Green for success, red for errors

### Interactive Elements

- **Hover Effects**: Cards lift and change border color
- **Click Feedback**: Toast notifications for user actions
- **Loading States**: Spinners during processing
- **Visual Indicators**: Connection status, recording state

## 🧪 Testing

### Test File Created

- `test_conflict_ui.html` - Standalone test for conflict resolution UI
- Simulates the complete conflict resolution flow
- Interactive testing without backend dependency

### Test Features

- Mock conflict data
- Interactive option selection
- Activity log to track user actions
- Test controls to simulate different scenarios

## 📱 Responsive Design

The conflict resolution panel is fully responsive:

- **Desktop**: Full-width cards with side-by-side layout
- **Tablet**: Stacked layout with touch-friendly buttons
- **Mobile**: Compact cards with vertical button layout

## 🔄 State Management

### Conflict Resolution States

1. **No Conflict**: Normal scheduling flow
2. **Conflict Detected**: Show options panel
3. **Option Selected**: Process selection and schedule
4. **Resolution Complete**: Hide panel and show confirmation

### Session Persistence

- Conflict data stored in component state
- Cleared after successful resolution or cancellation
- Survives component re-renders during the resolution process

## 🚀 Benefits

### For Users

- **Visual Feedback**: Clear indication of conflicts and options
- **Multiple Interaction Methods**: Voice commands + UI buttons
- **Intuitive Design**: Easy to understand and navigate
- **Immediate Response**: No waiting for voice processing

### For Developers

- **Modular Components**: Easy to extend and modify
- **Type Safety**: Full TypeScript support
- **Error Handling**: Graceful handling of edge cases
- **Maintainable Code**: Clean separation of concerns

## 📋 Summary

The frontend now provides a complete conflict resolution experience:

✅ **Visual conflict detection and display**
✅ **Interactive option selection (voice + UI)**
✅ **Real-time configuration sending**
✅ **Responsive design for all devices**
✅ **Comprehensive error handling**
✅ **User-friendly feedback and guidance**

The enhanced frontend seamlessly integrates with the backend conflict resolution system to provide users with a smooth, intuitive scheduling experience when conflicts arise.
