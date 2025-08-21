"use client";
import React, { useState, useRef, useCallback, useEffect, use } from "react";
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

// Enhanced interfaces from attached file
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

export default function EnhancedScheduleVoiceFramework() {
  const router = useRouter();

  // Enhanced state management from attached file
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

  // UI-specific states from new design
  const [selectedVoice, setSelectedVoice] = useState("en-IN-NeerjaNeural");
  const [selectedTimezone, setSelectedTimezone] = useState("UTC");

  // Enhanced refs from attached file
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<MediaRecorder | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const sessionStartTimeRef = useRef<number>(0);
  const lastPingRef = useRef<number>(0);
  const audioChunkCountRef = useRef<number>(0);
  const qualitySamplesRef = useRef<number[]>([]);

  // Audio processing constants from attached file
  const SAMPLE_RATE = 16000;
  const CHANNELS = 1;
  const RECONNECT_DELAY = 3000;

  // Configuration arrays from new design
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

  // Enhanced message display from attached file
  const addMessage = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setMessages((prev) => [...prev.slice(-19), `${timestamp}: ${message}`]);
  }, []);

  // Set user's actual timezone on mount
  useEffect(() => {
    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    setSelectedTimezone(userTimezone || "UTC");
  }, []);

  // Load meetings when timezone changes
  useEffect(() => {
    fetchAvailability();
  }, [selectedTimezone]);

  // Auto-connect WebSocket on mount (from attached file)
  useEffect(() => {
    connectWebSocket();
    return () => {
      cleanupResources();
    };
  }, []);

  // Enhanced WebSocket connection from attached file
  const connectWebSocket = useCallback(() => {
    try {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        console.log("🔗 WebSocket already connected");
        return;
      }

      setConnectionStatus("Connecting...");
      console.log("🔗 Connecting to: ws://localhost:8000/ws/voice-live");

      wsRef.current = new WebSocket("ws://localhost:8000/ws/voice-live");

      wsRef.current.onopen = () => {
        console.log("✅ WebSocket connected successfully");
        setIsConnected(true);
        setConnectionStatus("Connected");
        sessionStartTimeRef.current = Date.now();
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
        setIsRecording(false);
        setIsProcessing(false);
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
  }, []);

  // Enhanced WebSocket message handler from attached file
  const handleWebSocketMessage = async (data: AudioMessage) => {
    console.log("📨 Received:", data.type, data.message?.substring(0, 50));

    if (data.session_id && !sessionId) {
      setSessionId(data.session_id);
    }

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
          await fetchAvailability(); // Refresh meetings
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

  // Enhanced audio playback from attached file
  const playAudioFromHex = async (hexAudio: string): Promise<void> => {
    try {
      const audioData = new Uint8Array(
        hexAudio.match(/.{2}/g)?.map((byte) => parseInt(byte, 16)) || []
      );

      if (audioData.length === 0) {
        console.warn("⚠️ Empty audio data received");
        return;
      }

      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext ||
          (window as any).webkitAudioContext)();
      }

      if (audioContextRef.current.state === "suspended") {
        await audioContextRef.current.resume();
      }

      try {
        const audioBuffer = await audioContextRef.current.decodeAudioData(
          audioData.buffer.slice(0)
        );
        const source = audioContextRef.current.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContextRef.current.destination);
        source.start();
      } catch (decodeError) {
        const blob = new Blob([audioData], { type: "audio/wav" });
        const audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(audioUrl);
        audio.onended = () => URL.revokeObjectURL(audioUrl);
        await audio.play();
      }
    } catch (error) {
      console.error("🔊 Audio playback failed:", error);
    }
  };

  // Enhanced microphone initialization from attached file
  const initializeMicrophone = async (): Promise<MediaStream> => {
    try {
      console.log("🎤 Initializing enhanced microphone...");

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: CHANNELS,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;
      console.log("✅ Microphone initialized successfully");
      return stream;
    } catch (error) {
      console.error("❌ Microphone initialization failed:", error);
      throw new Error(`Microphone access failed: ${error}`);
    }
  };

  // Enhanced recording functions from attached file with volume boost
  const startRecording = async () => {
    if (!isConnected || isRecording) {
      toast.warning(
        "Cannot start recording: not connected or already recording"
      );
      return;
    }

    try {
      addMessage("🎤 Starting recording...");
      const stream = await initializeMicrophone();

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      const recorder = new MediaRecorder(stream, {
        mimeType: mimeType,
        audioBitsPerSecond: 128000,
      });

      processorRef.current = recorder;
      const audioChunks: Blob[] = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      recorder.onstop = async () => {
        console.log("⏹️ Processing complete recording...");

        if (audioChunks.length > 0) {
          try {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(
                JSON.stringify({
                  event: "start_processing",
                  timezone: selectedTimezone,
                })
              );
            }

            const audioBlob = new Blob(audioChunks, { type: mimeType });

            if (!audioContextRef.current) {
              audioContextRef.current = new (window.AudioContext ||
                (window as any).webkitAudioContext)({ sampleRate: 16000 });
            }

            if (audioContextRef.current.state === "suspended") {
              await audioContextRef.current.resume();
            }

            const arrayBuffer = await audioBlob.arrayBuffer();
            const audioBuffer = await audioContextRef.current.decodeAudioData(
              arrayBuffer
            );
            const channelData = audioBuffer.getChannelData(0);

            // Apply volume boost for quiet audio
            let finalChannelData = channelData;
            if (audioBuffer.sampleRate !== 16000) {
              finalChannelData = resampleTo16kHz(
                channelData,
                audioBuffer.sampleRate
              );
            }

            const pcmData = convertToCleanPCM16(finalChannelData);

            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(pcmData);
              addMessage(
                `📡 Sent clean audio: ${(pcmData.byteLength / 1024).toFixed(
                  1
                )} KB`
              );
            }

            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(JSON.stringify({ event: "end_processing" }));
            }
          } catch (error) {
            console.error("❌ Audio conversion error:", error);
            addMessage("❌ Failed to convert audio");
            toast.error("Failed to process audio");
          }
        }

        audioChunks.length = 0;
      };

      recorder.start();
      setIsRecording(true);
      addMessage("🔴 Recording started! Speak clearly...");
      toast.info("Recording started - speak your command");
    } catch (error) {
      console.error("❌ Recording start failed:", error);
      addMessage(`❌ Recording failed: ${error}`);
      toast.error("Recording failed");
    }
  };

  const stopRecording = async () => {
    if (!isRecording) return;

    try {
      console.log("⏹️ Stopping recording...");
      setIsRecording((prevState) => {
        console.log("Previous state:", prevState);
        return false;
      });
      if (processorRef.current && processorRef.current.state === "recording") {
        processorRef.current.stop();
      }

      addMessage("⏹️ Recording stopped, processing...");
      toast.info("Processing your speech...");
    } catch (error) {
      console.error("❌ Stop recording error:", error);
    }
  };

  // Helper functions for audio processing
  const convertToCleanPCM16 = (inputData: Float32Array): ArrayBuffer => {
    const length = inputData.length;
    const result = new Int16Array(length);

    const rms = Math.sqrt(
      inputData.reduce((sum, sample) => sum + sample * sample, 0) / length
    );

    let volumeBoost = 1.0;
    if (rms < 0.01) {
      volumeBoost = 10.0;
    } else if (rms < 0.05) {
      volumeBoost = 3.0;
    }

    for (let i = 0; i < length; i++) {
      let sample = inputData[i] * volumeBoost;
      sample = Math.max(-1.0, Math.min(1.0, sample));
      const pcmSample = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      result[i] = Math.floor(pcmSample);
    }

    return result.buffer;
  };

  const resampleTo16kHz = (
    inputData: Float32Array,
    originalSampleRate: number
  ): Float32Array => {
    if (originalSampleRate === 16000) return inputData;

    const ratio = originalSampleRate / 16000;
    const outputLength = Math.floor(inputData.length / ratio);
    const output = new Float32Array(outputLength);

    for (let i = 0; i < outputLength; i++) {
      const srcIndex = Math.floor(i * ratio);
      output[i] = inputData[srcIndex];
    }

    return output;
  };

  // Meeting management functions
  const fetchAvailability = async () => {
    setIsLoadingMeetings(true);
    try {
      const start = new Date().toISOString();
      const end = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();

      const response = await fetch(
        `http://localhost:8000/calendar/availability-test?start=${start}&end=${end}&timezone=${selectedTimezone}`
      );

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      const data = await response.json();

      if (data.availability) {
        setMeetings(
          data.availability.map((event: any) => ({
            title: event.title || "Scheduled Meeting",
            time: event.start.split("T")[1]?.slice(0, 5) || "00:00",
            status: event.status || "scheduled",
            date: event.start.split("T"),
            participants: event.attendees?.length + 1 || 1,
            description: event.description || "",
            location: event.location || "",
            attendees: event.attendees || [],
            organizer: event.organizer || "",
            creator: event.creator || "",
            created: event.created || "",
            updated: event.updated || "",
            htmlLink: event.htmlLink || "",
            hangoutLink: event.hangoutLink || "",
            recurrence: event.recurrence || [],
            recurringEventId: event.recurringEventId || "",
            endTime: event.end.split("T")[1]?.slice(0, 5) || "00:00",
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
      addMessage(`📅 Meeting "${details.title}" scheduled successfully!`);
      addMessage(`🕐 Time: ${details.start} - ${details.end}`);
      if (details.attendees) {
        addMessage(`👥 Attendees: ${details.attendees.join(", ")}`);
      }
    }
  };

  // Cleanup function
  const cleanupResources = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
  };

  // Quality indicators from attached file
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
  // Also add this to see when the component re-renders
  useEffect(() => {
    console.log("isRecording changed to:", isRecording);
  }, [isRecording]);
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Enhanced Header with connection status */}
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

            {/* Connection status indicator */}
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
            {/* Enhanced Voice Assistant Card */}
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
                {/* Recording Button */}
                <div className="flex justify-center">
                  <div className="relative">
                    <Button
                      onClick={isRecording ? stopRecording : startRecording}
                      size="lg"
                      disabled={!isConnected && !isRecording}
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
                        <div className="absolute -inset-4 rounded-full border border-red-200 animate-ping animation-delay-300"></div>
                      </>
                    )}

                    {isProcessing && (
                      <div className="absolute -inset-6 rounded-full border-2 border-yellow-400 animate-spin">
                        <Loader2 className="w-4 h-4 text-yellow-600" />
                      </div>
                    )}
                  </div>
                </div>

                {/* Configuration Controls */}
                <div className="grid md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700 flex items-center gap-2">
                      <Volume2 className="w-4 h-4" />
                      Voice Selection
                    </label>
                    <Select
                      value={selectedVoice}
                      onValueChange={setSelectedVoice}
                    >
                      <SelectTrigger className="border-slate-200 hover:border-slate-300 transition-colors">
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
                      <Globe className="w-4 h-4" />
                      Timezone
                    </label>
                    <Select
                      value={selectedTimezone}
                      onValueChange={setSelectedTimezone}
                    >
                      <SelectTrigger className="border-slate-200 hover:border-slate-300 transition-colors">
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

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700 flex items-center gap-2">
                      <Settings className="w-4 h-4" />
                      Connection Quality
                    </label>
                    <div
                      className={`px-3 py-2 rounded-md text-sm font-medium transition-all duration-300 ${
                        isConnected
                          ? "bg-green-50 text-green-700 border border-green-200"
                          : "bg-red-50 text-red-600 border border-red-200"
                      }`}
                    >
                      {getConnectionQuality()}
                    </div>
                  </div>
                </div>

                {/* Live Transcription */}
                <div className="space-y-3">
                  <label className="text-sm font-medium text-slate-700">
                    Live Transcription
                  </label>
                  <div className="min-h-[100px] p-4 bg-slate-50 rounded-lg border border-slate-200">
                    {transcription ? (
                      <p className="text-slate-800 animate-fade-in">
                        {transcription}
                      </p>
                    ) : (
                      <p className="text-slate-400 italic">
                        Transcription will appear here when you start
                        speaking...
                      </p>
                    )}
                  </div>
                </div>

                {/* Activity Messages */}
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
                        messages.slice(-5).map((msg, idx) => (
                          <div key={idx} className="text-sm text-slate-600">
                            {msg}
                          </div>
                        ))
                      )}
                    </div>
                  </ScrollArea>
                </div>
              </CardContent>
            </Card>

            {/* Voice Commands Card */}
            <Card className="border-0 shadow-lg bg-white/70 backdrop-blur-sm hover:shadow-xl transition-all duration-300">
              <CardHeader>
                <CardTitle className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                  <Mic className="w-5 h-5" />
                  Voice Commands
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 gap-4">
                  {voiceCommands.map((cmd, index) => (
                    <div
                      key={index}
                      className="p-3 bg-slate-50 rounded-lg border border-slate-200 hover:bg-slate-100 transition-colors"
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

          {/* Right Sidebar */}
          <div className="space-y-6">
            {/* Meetings Card */}
            <Card className="border-0 shadow-lg bg-white/70 backdrop-blur-sm hover:shadow-xl transition-all duration-300">
              <CardHeader>
                <CardTitle className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                  <Calendar className="w-5 h-5" />
                  Upcoming Meetings
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
                        <p>No meetings found</p>
                        <p className="text-sm">
                          Try scheduling one with voice commands
                        </p>
                      </div>
                    ) : (
                      meetings.map((meeting, index) => (
                        <div
                          key={`${meeting.date}-${meeting.time}-${index}`}
                          className="p-4 rounded-lg border border-slate-200 hover:border-slate-300 transition-all duration-200 hover:shadow-md bg-white/50"
                        >
                          <div className="flex items-start justify-between mb-2">
                            <h4 className="font-medium text-slate-800">
                              {meeting.title}
                              {meeting.date && (
                                <span className="text-sm text-slate-500 ml-2">
                                  ({meeting.date})
                                </span>
                              )}
                            </h4>
                            <Badge
                              variant={
                                meeting.status === "confirmed"
                                  ? "default"
                                  : "destructive"
                              }
                              className={`${
                                meeting.status === "confirmed"
                                  ? "bg-green-100 text-green-800 hover:bg-green-200"
                                  : "bg-red-100 text-red-800 hover:bg-red-200"
                              } transition-colors`}
                            >
                              {meeting.status === "confirmed" ? (
                                <CheckCircle className="w-3 h-3 mr-1" />
                              ) : (
                                <XCircle className="w-3 h-3 mr-1" />
                              )}
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
                          {meeting.location && (
                            <div className="text-sm text-slate-600 mt-1">
                              📍 {meeting.location}
                            </div>
                          )}
                          {meeting.description && (
                            <div className="text-sm text-slate-600 mt-1">
                              {meeting.description}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Quick Stats Card */}
            <Card className="border-0 shadow-lg bg-white/70 backdrop-blur-sm hover:shadow-xl transition-all duration-300">
              <CardHeader>
                <CardTitle className="text-lg font-semibold text-slate-800">
                  Quick Stats
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600">Scheduled Today</span>
                    <span className="font-semibold text-green-600">
                      {meetings.filter((m) => m.status === "scheduled").length}
                    </span>
                  </div>
                  <Separator />
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600">Audio Quality</span>
                    <span className="font-semibold text-blue-600">
                      {getAudioQuality()}
                    </span>
                  </div>
                  <Separator />
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600">Session Duration</span>
                    <span className="font-semibold text-indigo-600">
                      {Math.round(connectionStats.sessionDuration)}s
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
