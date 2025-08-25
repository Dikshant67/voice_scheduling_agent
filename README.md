# Voice Scheduling Agent Information

## Summary

A voice-enabled scheduling assistant application that uses speech recognition and natural language processing to help users schedule meetings. The application consists of a Next.js frontend and a FastAPI backend with Azure Cognitive Services integration for speech-to-text and text-to-voice capabilities.

## Structure

- **backend/**: Python FastAPI server with speech processing and calendar integration
- **frontend/**: Next.js web application with React components
- **.zencoder/**: Configuration directory for Zencoder

## Repository Components

- **Voice Processing**: Azure Cognitive Services for speech-to-text and text-to-voice
- **Calendar Integration**: Google Calendar API integration for scheduling
- **Conversational AI**: GPT-based agent for natural language understanding

## Projects

### Frontend (Next.js)

**Configuration File**: frontend/package.json

#### Language & Runtime

**Language**: TypeScript/JavaScript
**Version**: TypeScript 5.x
**Framework**: Next.js 15.2.4
**Package Manager**: npm/pnpm

#### Dependencies

**Main Dependencies**:

- React 18.2.0
- Next.js 15.2.4
- Radix UI components
- @react-oauth/google 0.12.2
- date-fns 4.1.0
- Tailwind CSS

#### Build & Installation

```bash
cd frontend
npm install
npm run dev    # Development
npm run build  # Production build
npm start      # Production server
```

#### Testing

No dedicated testing framework found in the frontend project.

### Backend (FastAPI)

**Configuration File**: backend/requirements.txt

#### Language & Runtime

**Language**: Python
**Version**: Python 3.10+
**Framework**: FastAPI 0.116.1
**Package Manager**: pip

#### Dependencies

**Main Dependencies**:

- fastapi 0.116.1
- uvicorn 0.35.0
- azure-cognitiveservices-speech 1.45.0
- google-api-python-client 2.177.0
- openai 1.98.0
- python-dotenv 1.1.1
- pydantic 2.11.7

#### Build & Installation

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python main.py
```

#### Testing

**Framework**: Python's built-in unittest (implied from test file naming)
**Test Location**: backend/tests/
**Naming Convention**: test\_\*.py
**Run Command**:

```bash
cd backend
python -m unittest discover tests
```

## Main Files & Resources

### Frontend

- **Entry Point**: frontend/app/page.tsx
- **Components**: frontend/components/
- **Styles**: frontend/styles/globals.css
- **Public Assets**: frontend/public/

### Backend

- **Entry Point**: backend/main.py
- **Core Logic**: backend/core/
- **Configuration**: backend/config/
- **Data Storage**: backend/data/

```

```
