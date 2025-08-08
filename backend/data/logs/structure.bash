schedule_meeting_by_voice/
│
├── config/
│   └── config.py                 # API keys, constants, and time zone settings
│
├── core/
│   ├── voice_to_text.py         # Speech-to-text (STT) logic (Azure / Whisper)
│   ├── text_to_voice.py         # Text-to-speech (TTS) logic (Azure)
│   ├── run_gpt_agent.py         # GPT-4o interaction (intent + entity extraction)
│   ├── calendar_service.py      # Google Calendar API integration
│   ├── timezone_utils.py        # Time zone handling, conversions
│   └── validation.py   
|    └── conversation_flow.py            # Title, date, time validations
│
├── flow/
│       # Main interaction loop (GPT → calendar → response)
│
├── data/
│   └── logs/                    # Interaction and error logs
│   └── history.json             # Optional: Store past meetings
│
├── tests/
│   ├── test_calendar.py         # Unit tests for calendar scheduling
│   └── test_gpt_agent.py        # Tests for prompt→response logic
│
├── .env                         # Secrets (never push to GitHub)
├── .gitignore
├── main.py                      # Starts the assistant
├── requirements.txt
└── README.md
