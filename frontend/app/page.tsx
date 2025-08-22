"use client";
import React, { useState, useRef, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Mic,
  MicOff,
  Calendar,
  Clock,
  Users,
  CheckCircle,
  XCircle,
  Globe,
  Volume2,
  Sparkles,
  Loader2,
  Settings,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import GoogleLoginButton from "@/components/ui/google_login_button";

// --- Interfaces (Unchanged) ---
interface AudioMessage {
  type: string;
  message?: string;
  audio?: string;
  audio_duration?: number;
  status?: string;
  text?: string;
  confidence?: string;
  event_details?: any;
  chunk_count?: number;
  chunk_size?: number;
  total_bytes?: number;
  duration?: number;
  quality?: number;
  is_silent?: boolean;
  session_id?: string;
  timestamp?: string;
}

interface AudioFeedback {
  chunk_count: number;
  total_bytes: number;
  duration: number;
  quality: number;
  is_silent: boolean;
}

interface Meeting {
  title: string;
  time: string;
  status: string;
  date: string;
  participants: number;
  description: string;
  location: string;
  attendees: Array<{ email: string; responseStatus: string }>;
  organizer: string;
  creator: string;
  created: string;
  updated: string;
  htmlLink: string;
  hangoutLink: string;
  recurrence: string[];
  recurringEventId: string;
  endTime: string;
}

interface VoiceCommand {
  command: string;
  description: string;
}

interface ConnectionStats {
  packetsLost: number;
  averageLatency: number;
  audioQuality: number;
  sessionDuration: number;
}

// --- NEW: Audio Worklet Code ---
// This code runs in a separate thread to process audio efficiently.
const audioWorkletProcessorCode = `
  class AudioStreamerProcessor extends AudioWorkletProcessor {
    constructor() {
      super();
      this.bufferSize = 2048;
      this._buffer = new Int16Array(this.bufferSize);
      this._pos = 0;
    }

    // Converts Float32Array to Int16Array (PCM16)
    floatTo16BitPCM(input) {
      const output = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      return output;
    }

    process(inputs, outputs, parameters) {
      const input = inputs[0];
      if (input.length > 0) {
        const channelData = input[0];
        if(channelData) {
            const pcmData = this.floatTo16BitPCM(channelData);
            // Post the raw PCM16 data back to the main thread
            this.port.postMessage(pcmData);
        }
      }
      return true;
    }
  }
  registerProcessor('audio-streamer-processor', AudioStreamerProcessor);
`;

export default function EnhancedScheduleVoiceFramework() {
  const router = useRouter();

  // --- State Management (Mostly Unchanged) ---
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [messages, setMessages] = useState<string[]>([]);
  const [transcription, setTranscription] = useState("");
  const [connectionStatus, setConnectionStatus] =
    useState<string>("Disconnected");
  const [audioFeedback, setAudioFeedback] = useState<AudioFeedback | null>(
    null
  );
  const [connectionStats, setConnectionStats] = useState<ConnectionStats>({
    packetsLost: 0,
    averageLatency: 0,
    audioQuality: 0,
    sessionDuration: 0,
  });
  const [sessionId, setSessionId] = useState<string>("");
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [isLoadingMeetings, setIsLoadingMeetings] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState("en-IN-NeerjaNeural");
  const [selectedTimezone, setSelectedTimezone] = useState("UTC");

  // --- Refs ---
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null); // Ref for the worklet node
  const mediaStreamSourceRef = useRef<MediaStreamAudioSourceNode | null>(null); // Ref for the audio source

  // Audio processing constants
  const SAMPLE_RATE = 16000;

  // --- Configuration Arrays (Unchanged) ---
  const voiceCommands: VoiceCommand[] = [
    { command: "Schedule meeting", description: "Create a new meeting" },
    { command: "Cancel meeting", description: "Cancel existing meeting" },
    { command: "List meetings", description: "Show all meetings" },
    { command: "Set reminder", description: "Add meeting reminder" },
  ];
  const voices = [
    { value: "en-IN-NeerjaNeural", label: "English (India) - Female" },
    { value: "en-US-JennyNeural", label: "English (US) - Female" },
    { value: "en-US-GuyNeural", label: "English (US) - Male" },
    { value: "en-GB-SoniaNeural", label: "English (UK) - Female" },
  ];
  const timezones = [
    { value: "America/Los_Angeles", label: "UTC-8 (PST)" },
    { value: "America/New_York", label: "UTC-5 (EST)" },
    { value: "UTC", label: "UTC+0 (GMT)" },
    { value: "Europe/Paris", label: "UTC+1 (CET)" },
    { value: "Asia/Kolkata", label: "UTC+5:30 (IST)" },
  ];

  // --- Core Functions (partially modified) ---
  const addMessage = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setMessages((prev) => [...prev.slice(-19), `${timestamp}: ${message}`]);
  }, []);

  const cleanupResources = useCallback(() => {
    console.log("[STREAM] Cleaning up all audio and WebSocket resources.");
    // Stop microphone tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    // Disconnect and close AudioContext
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      workletNodeRef.current?.port.close();
      workletNodeRef.current?.disconnect();
      mediaStreamSourceRef.current?.disconnect();
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  // --- WebSocket Logic (partially modified) ---
  const connectWebSocket = useCallback(() => {
    try {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        console.log("🔗 WebSocket already connected");
        return;
      }

      setConnectionStatus("Connecting...");
      console.log("🔗 Connecting to: ws://localhost:8000/ws/voice-live");
      wsRef.current = new WebSocket("ws://localhost:8000/ws/voice-live");
      wsRef.current.binaryType = "arraybuffer"; // Important for sending raw audio

      wsRef.current.onopen = () => {
        console.log("✅ WebSocket connected successfully");
        setIsConnected(true);
        setConnectionStatus("Connected");
        addMessage("🟢 Connected to enhanced voice assistant");
        toast.success("Connected to voice assistant");
      };

      wsRef.current.onmessage = async (event) => {
        try {
          const data: AudioMessage = JSON.parse(event.data);
          await handleWebSocketMessage(data);
        } catch (error) {
          console.error("❌ Error parsing WebSocket message:", error);
          addMessage(`⚠️ Message parsing error: ${error}`);
        }
      };

      wsRef.current.onclose = (event) => {
        console.log(`🔌 WebSocket disconnected: Code ${event.code}`);
        setIsConnected(false);
        setConnectionStatus("Disconnected");
        if (isRecording) {
          stopRecording(false); // Stop recording if connection drops
        }
        addMessage(`🔴 Disconnected (Code: ${event.code})`);
        toast.error("Voice assistant disconnected");
      };

      wsRef.current.onerror = (error) => {
        console.error("💥 WebSocket error:", error);
        setConnectionStatus("Connection Error");
        addMessage("❌ Connection error occurred");
        toast.error("Connection error occurred");
      };
    } catch (error) {
      console.error("❌ Failed to create WebSocket:", error);
      setConnectionStatus("Failed to Connect");
      toast.error("Failed to connect to voice assistant");
    }
  }, [isRecording]); // isRecording added to dependencies

  const handleWebSocketMessage = async (data: AudioMessage) => {
    console.log(
      "📨 [BACKEND] Received:",
      data.type,
      data.message?.substring(0, 50)
    );
    setSessionId(data.session_id || sessionId);

    switch (data.type) {
      case "greeting":
        addMessage(data.message || "Enhanced assistant ready");
        if (data.audio) await playAudioFromHex(data.audio);
        break;
      case "transcription":
        setTranscription(data.text || "");
        addMessage(`💬 You said: "${data.text}"`);
        toast.info("Speech recognized");
        break;
      case "processing_started":
        setIsProcessing(true);
        addMessage("🔄 Processing your speech...");
        break;
      case "meeting_result":
        setIsProcessing(false);
        addMessage(data.message || "✅ Meeting processed");
        if (data.audio) await playAudioFromHex(data.audio);
        if (data.event_details) {
          displayMeetingDetails(data.event_details);
          await fetchAvailability();
        }
        toast.success("Meeting scheduled successfully");
        break;
      case "unclear_speech":
      case "insufficient_audio":
      case "processing_error":
        setIsProcessing(false);
        addMessage(`💭 ${data.message}`);
        if (data.audio) await playAudioFromHex(data.audio);
        toast.warning(data.message || "Please try again");
        break;
      case "error":
        setIsProcessing(false);
        addMessage(`❌ Error: ${data.message}`);
        if (data.audio) await playAudioFromHex(data.audio);
        toast.error(data.message || "An error occurred");
        break;
      default:
        console.log("🤷 Unknown message type:", data.type);
        break;
    }
  };

  // --- Audio Playback (Unchanged) ---
  const playAudioFromHex = async (hexAudio: string): Promise<void> => {
    try {
      const audioData = new Uint8Array(
        hexAudio.match(/.{2}/g)?.map((byte) => parseInt(byte, 16)) || []
      );
      if (audioData.length === 0) return;
      const tempAudioContext = new (window.AudioContext ||
        (window as any).webkitAudioContext)();
      const audioBuffer = await tempAudioContext.decodeAudioData(
        audioData.buffer
      );
      const source = tempAudioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(tempAudioContext.destination);
      source.start(0);
      source.onended = () => tempAudioContext.close();
    } catch (error) {
      console.error("🔊 Audio playback failed:", error);
    }
  };

  // --- REWRITTEN: Live Streaming Recording Logic ---
  const startRecording = async () => {
    if (!isConnected || isRecording) {
      toast.warning(
        "Cannot start recording: not connected or already recording"
      );
      return;
    }

    setTranscription(""); // Clear previous transcription
    setIsRecording(true);
    addMessage("🎤 Starting live audio stream...");
    console.log("[STREAM] Starting recording...");

    try {
      // 1. Get User Media
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      // 2. Create Audio Context and Worklet
      audioContextRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });
      const processorBlob = new Blob([audioWorkletProcessorCode], {
        type: "application/javascript",
      });
      const processorUrl = URL.createObjectURL(processorBlob);
      await audioContextRef.current.audioWorklet.addModule(processorUrl);

      workletNodeRef.current = new AudioWorkletNode(
        audioContextRef.current,
        "audio-streamer-processor"
      );
      console.log("[STREAM] AudioWorklet node created.");

      // 3. Set up the message listener to stream data to WebSocket
      workletNodeRef.current.port.onmessage = (event) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const audioData = event.data;
          wsRef.current.send(audioData.buffer);
        }
      };

      // 4. Connect the audio graph: Mic -> Worklet
      mediaStreamSourceRef.current =
        audioContextRef.current.createMediaStreamSource(stream);
      mediaStreamSourceRef.current.connect(workletNodeRef.current);
      console.log("[STREAM] Audio graph connected.");

      // 5. Send control message to backend
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            event: "start_recording",
            timezone: selectedTimezone,
          })
        );
        console.log(
          `[STREAM] Sent 'start_recording' message with timezone: ${selectedTimezone}`
        );
      }

      addMessage("🔴 Live stream active! Speak now...");
      toast.info("Recording started - speak your command");
    } catch (error) {
      console.error("❌ [STREAM] Failed to start recording:", error);
      addMessage(`❌ Recording failed: ${error}`);
      toast.error("Microphone access denied or failed.");
      setIsRecording(false);
      cleanupResources();
    }
  };

  const stopRecording = async (sendMessage = true) => {
    if (!isRecording) return;

    console.log("[STREAM] Stopping recording...");
    setIsRecording(false);
    addMessage("⏹️ Stopping live stream, preparing for processing...");

    // 1. Send control message to backend
    if (sendMessage && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event: "stop_recording" }));
      console.log("[STREAM] Sent 'stop_recording' message.");
      toast.info("Processing your speech...");
    }

    // 2. Cleanup audio resources
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      workletNodeRef.current?.port.close();
      mediaStreamSourceRef.current?.disconnect();
      workletNodeRef.current?.disconnect();
      await audioContextRef.current.close();
      audioContextRef.current = null;
      console.log("[STREAM] AudioContext closed and resources released.");
    }
  };

  // --- Meeting and UI Helper Functions (Unchanged) ---
  const fetchAvailability = async () => {
    setIsLoadingMeetings(true);
    try {
      const start = new Date().toISOString();
      const end = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
      const response = await fetch(
        `http://localhost:8000/calendar/availability-test?start=${start}&end=${end}&timezone=${selectedTimezone}`
      );
      if (!response.ok) throw new Error(`HTTP error: ${response.status}`);
      const data = await response.json();
      if (data.availability) {
        setMeetings(
          data.availability.map((event: any) => ({
            title: event.summary || "Scheduled Meeting",
            time: new Date(event.start.dateTime).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
            }),
            status: event.status || "confirmed",
            date: new Date(event.start.dateTime).toLocaleDateString(),
            participants: event.attendees?.length || 1,
            description: event.description || "",
            location: event.location || "",
            attendees: event.attendees || [],
            organizer: event.organizer?.email || "",
            creator: event.creator?.email || "",
            created: event.created || "",
            updated: event.updated || "",
            htmlLink: event.htmlLink || "",
            hangoutLink: event.hangoutLink || "",
            recurrence: event.recurrence || [],
            recurringEventId: event.recurringEventId || "",
            endTime: new Date(event.end.dateTime).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
            }),
          }))
        );
      }
    } catch (error) {
      console.error("Fetch error:", error);
      toast.error("Failed to load meetings");
    } finally {
      setIsLoadingMeetings(false);
    }
  };

  const displayMeetingDetails = (details: any) => {
    if (details.status === "success") {
      addMessage(
        `📅 Meeting "${details.event_details.summary}" scheduled successfully!`
      );
      addMessage(
        `🕐 Time: ${new Date(
          details.event_details.start.dateTime
        ).toLocaleString()} - ${new Date(
          details.event_details.end.dateTime
        ).toLocaleString()}`
      );
      if (details.event_details.attendees) {
        addMessage(
          `👥 Attendees: ${details.event_details.attendees
            .map((a: any) => a.email)
            .join(", ")}`
        );
      }
    }
  };

  const getConnectionQuality = (): string => {
    if (!isConnected) return "disconnected";
    if (connectionStats.averageLatency > 1000) return "poor";
    if (connectionStats.averageLatency > 500) return "fair";
    return "excellent";
  };

  const getAudioQuality = (): string => {
    if (!audioFeedback) return "unknown";
    if (audioFeedback.quality > 1000) return "excellent";
    if (audioFeedback.quality > 500) return "good";
    if (audioFeedback.quality > 200) return "fair";
    return "poor";
  };

  // --- useEffect Hooks ---
  useEffect(() => {
    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    setSelectedTimezone(userTimezone || "UTC");
  }, []);

  useEffect(() => {
    if (isConnected) fetchAvailability();
  }, [selectedTimezone, isConnected]);

  useEffect(() => {
    connectWebSocket();
    return () => {
      cleanupResources();
    };
  }, []); // Empty dependency array ensures this runs only once on mount

  useEffect(() => {
    console.log("[STATE] isRecording changed to:", isRecording);
  }, [isRecording]);

  // --- JSX (UI) ---
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-slate-800 to-slate-600 bg-clip-text text-transparent">
                  Schedule
                </h1>
                <p className="text-sm text-slate-500">
                  Voice-Powered Meeting Assistant
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div
                  className={`w-2 h-2 rounded-full ${
                    isConnected ? "bg-green-500" : "bg-red-500"
                  }`}
                ></div>
                <span className="text-sm text-slate-600">
                  {connectionStatus}
                </span>
              </div>
              <GoogleLoginButton children={undefined} />
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8">
        <div className="grid lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm hover:shadow-2xl transition-all duration-500">
              <CardHeader className="text-center pb-6">
                <CardTitle className="text-2xl font-semibold text-slate-800">
                  Enhanced Voice Assistant
                </CardTitle>
                <p className="text-slate-600">
                  Speak naturally to schedule or manage your meetings
                </p>
              </CardHeader>
              <CardContent className="space-y-8">
                <div className="flex justify-center">
                  <div className="relative">
                    <Button
                      onClick={
                        isRecording ? () => stopRecording() : startRecording
                      }
                      size="lg"
                      disabled={!isConnected}
                      className={`w-24 h-24 rounded-full transition-all duration-300 ${
                        isRecording
                          ? "bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 shadow-lg shadow-red-500/25"
                          : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-lg shadow-blue-500/25"
                      } hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {isRecording ? (
                        <MicOff className="w-8 h-8 text-white" />
                      ) : (
                        <Mic className="w-8 h-8 text-white" />
                      )}
                    </Button>
                    {isRecording && (
                      <>
                        <div className="absolute inset-0 rounded-full border-4 border-red-400 animate-ping opacity-75"></div>
                        <div className="absolute inset-0 rounded-full border-2 border-red-300 animate-pulse"></div>
                      </>
                    )}
                    {isProcessing && (
                      <div className="absolute -inset-4 flex items-center justify-center">
                        <Loader2 className="w-8 h-8 text-yellow-500 animate-spin" />
                      </div>
                    )}
                  </div>
                </div>

                <div className="grid md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700 flex items-center gap-2">
                      <Volume2 className="w-4 h-4" /> Voice Selection
                    </label>
                    <Select
                      value={selectedVoice}
                      onValueChange={setSelectedVoice}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {voices.map((voice) => (
                          <SelectItem key={voice.value} value={voice.value}>
                            {voice.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700 flex items-center gap-2">
                      <Globe className="w-4 h-4" /> Timezone
                    </label>
                    <Select
                      value={selectedTimezone}
                      onValueChange={setSelectedTimezone}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {timezones.map((timezone) => (
                          <SelectItem
                            key={timezone.value}
                            value={timezone.value}
                          >
                            {timezone.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="text-sm font-medium text-slate-700">
                    Live Transcription
                  </label>
                  <div className="min-h-[100px] p-4 bg-slate-50 rounded-lg border border-slate-200">
                    {transcription ? (
                      <p className="text-slate-800">{transcription}</p>
                    ) : (
                      <p className="text-slate-400 italic">
                        {isRecording
                          ? "Listening..."
                          : "Press the mic and speak to see transcription..."}
                      </p>
                    )}
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="text-sm font-medium text-slate-700">
                    Activity Log
                  </label>
                  <ScrollArea className="h-32 p-4 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="space-y-1">
                      {messages.length === 0 ? (
                        <p className="text-slate-400 italic text-sm">
                          Activity messages will appear here...
                        </p>
                      ) : (
                        messages.map((msg, idx) => (
                          <div
                            key={idx}
                            className="text-sm text-slate-600 font-mono"
                          >
                            {msg}
                          </div>
                        ))
                      )}
                    </div>
                  </ScrollArea>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-lg bg-white/70 backdrop-blur-sm">
              <CardHeader>
                <CardTitle className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                  <Mic className="w-5 h-5" /> Voice Commands
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 gap-4">
                  {voiceCommands.map((cmd, index) => (
                    <div
                      key={index}
                      className="p-3 bg-slate-50 rounded-lg border border-slate-200"
                    >
                      <p className="font-medium text-slate-800">
                        "{cmd.command}"
                      </p>
                      <p className="text-sm text-slate-600">
                        {cmd.description}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card className="border-0 shadow-lg bg-white/70 backdrop-blur-sm">
              <CardHeader>
                <CardTitle className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                  <Calendar className="w-5 h-5" /> Upcoming Meetings
                  {isLoadingMeetings && (
                    <Loader2 className="w-4 h-4 animate-spin ml-2" />
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px]">
                  <div className="space-y-4">
                    {meetings.length === 0 ? (
                      <div className="text-center text-slate-500 py-8">
                        <Calendar className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                        <p>No upcoming meetings found</p>
                      </div>
                    ) : (
                      meetings.map((meeting, index) => (
                        <div
                          key={index}
                          className="p-4 rounded-lg border border-slate-200 bg-white/50"
                        >
                          <div className="flex items-start justify-between mb-2">
                            <h4 className="font-medium text-slate-800">
                              {meeting.title}
                            </h4>
                            <Badge
                              variant={
                                meeting.status === "confirmed"
                                  ? "default"
                                  : "destructive"
                              }
                            >
                              {meeting.status}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-4 text-sm text-slate-600">
                            <div className="flex items-center gap-1">
                              <Clock className="w-4 h-4" />
                              {meeting.time} - {meeting.endTime}
                            </div>
                            <div className="flex items-center gap-1">
                              <Users className="w-4 h-4" />
                              {meeting.participants}
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
