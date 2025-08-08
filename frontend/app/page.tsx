"use client";

import { useState, useEffect } from "react";
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
} from "lucide-react";
import GoogleLoginButton from "@/components/ui/google_login_button";

interface Meeting {
  id: string;
  title: string;
  time: string;
  date?: string; // Optional date field
  status: "scheduled" | "canceled";
  participants: number;
}

interface VoiceCommand {
  command: string;
  description: string;
}

export default function ScheduleVoiceFramework() {
  const [isRecording, setIsRecording] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState("en-IN-NeerjaNeural");
  const [selectedTimezone, setSelectedTimezone] = useState("UTC");
  const [transcription, setTranscription] = useState("");
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);

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

  useEffect(() => {
    // Set timezone client-side
    setSelectedTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");

    // Fetch availability
    const fetchAvailability = async () => {
      try {
        const start = new Date().toISOString();
        const end = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
        const response = await fetch(
          `http://localhost:8000/calendar/availability?start=${start}&end=${end}&timezone=${selectedTimezone}`
        );
        const data = await response.json();
        if (data.availability) {
          setMeetings(
            data.availability.map((event: any, index: number) => ({
              id: `${index}-${event.start}`,
              title: event.summary || "Unnamed Meeting",
              time: event.start.split("T")[1].slice(0, 5),
              status: "scheduled",
              date: event.start.split("T")[0],
              participants: event.attendees?.length || 1,
            }))
          );
        }
      } catch (error) {
        setTranscription(`Error fetching availability: ${error}`);
      }
    };
    fetchAvailability();

    // Cleanup WebSocket, recorder, and media stream
    return () => {
      if (ws) ws.close();
      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
      }
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [selectedTimezone]);

  // const toggleRecording = async () => {
  //   if (!isRecording) {
  //     // Start recording
  //     try {
  //       const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  //       setMediaStream(stream); // Store the stream for cleanup
  //       const recorder = new MediaRecorder(stream);
  //       setMediaRecorder(recorder);
  //       const audioChunks: Blob[] = [];

  //       recorder.ondataavailable = (event) => {
  //         audioChunks.push(event.data);
  //       };

  //       recorder.onstop = async () => {
  //         const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
  //         const arrayBuffer = await audioBlob.arrayBuffer();
  //         const audioHex = Array.from(new Uint8Array(arrayBuffer))
  //           .map((b) => b.toString(16).padStart(2, "0"))
  //           .join("");

  //         const websocket = new WebSocket("ws://localhost:8000/ws/voice");
  //         setWs(websocket);

  //         websocket.onopen = () => {
  //           websocket.send(
  //             JSON.stringify({
  //               audio: audioHex,
  //               timezone: selectedTimezone,
  //             })
  //           );
  //         };

  //         websocket.onmessage = (event) => {
  //           const data = JSON.parse(event.data);
  //           if (data.error) {
  //             setTranscription(`Error: ${data.error}`);
  //           } else if (data.status === "scheduled") {
  //             setTranscription(
  //               `Meeting scheduled: ${data.event.start} (${selectedTimezone})`
  //             );
  //             setMeetings((prev) => [
  //               ...prev,
  //               {
  //                 id: data.event.link || `meeting-${Date.now()}-${prev.length}`,
  //                 title: data.event.summary || "New Meeting",
  //                 time: data.event.start.split(" ")[1],
  //                 status: "scheduled",
  //                 participants: data.event.attendees?.length || 1,
  //               },
  //             ]);
  //           } else if (data.status === "conflict") {
  //             setTranscription(
  //               `${data.event.message}. Suggested: ${data.event.suggested_start} (${selectedTimezone})`
  //             );
  //           } else if (data.status === "missing_info") {
  //             setTranscription(data.event.message);
  //           }

  //           if (data.audio) {
  //             const audioBytes = new Uint8Array(
  //               data.audio.match(/.{1,2}/g).map((byte: string) => parseInt(byte, 16))
  //             );
  //             const audioBlob = new Blob([audioBytes], { type: "audio/wav" });
  //             const audioUrl = URL.createObjectURL(audioBlob);
  //             const audio = new Audio(audioUrl);
  //             audio.play();
  //           }
  //         };

  //         websocket.onerror = () => {
  //           setTranscription("WebSocket error. Please try again.");
  //           setIsRecording(false);
  //         };

  //         websocket.onclose = () => {
  //           setWs(null);
  //         };
  //       };

  //       recorder.start();
  //       setIsRecording(true);
  //       setTranscription("Listening...");
  //     } catch (error) {
  //       setTranscription(`Error accessing microphone: ${error}`);
  //       setIsRecording(false);
  //     }
  //   } else {
  //     // Stop recording
  //     if (mediaRecorder && mediaRecorder.state !== "inactive") {
  //       mediaRecorder.stop();
  //     }
  //     if (mediaStream) {
  //       mediaStream.getTracks().forEach((track) => track.stop());
  //     }
  //     if (ws) {
  //       ws.close();
  //     }
  //     setMediaRecorder(null);
  //     setMediaStream(null);
  //     setWs(null);
  //     setIsRecording(false);
  //     setTranscription("Recording stopped.");
  //   }
  // };
const toggleRecording = async () => {
  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      setMediaRecorder(recorder);
      const audioChunks: Blob[] = [];

      recorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
        const arrayBuffer = await audioBlob.arrayBuffer();
        const audioHex = Array.from(new Uint8Array(arrayBuffer))
          .map((b) => b.toString(16).padStart(2, "0"))
          .join("");

        const websocket = new WebSocket("ws://localhost:8000/ws/voice");
        setWs(websocket);

        websocket.onopen = () => {
          websocket.send(
            JSON.stringify({
              audio: audioHex,
              timezone: selectedTimezone,
            })
          );
        };

        websocket.onmessage = (event) => {
          const data = JSON.parse(event.data);
          if (data.error) {
            setTranscription(`Error: ${data.error}`);
          } else if (data.status === "scheduled") {
            setTranscription(`Meeting scheduled: ${data.event.start} (${selectedTimezone})`);
            setMeetings((prev) => [
              ...prev,
              {
                id: data.event.link || `meeting-${Date.now()}-${prev.length}`,
                title: data.event.summary || "New Meeting",
                time: data.event.start.split(" ")[1],
                status: "scheduled",
                participants: data.event.attendees?.length || 1,
              },
            ]);
          } else if (data.status === "conflict") {
            setTranscription(
              `${data.event.message}. Suggested: ${data.event.suggested_start} (${selectedTimezone})`
            );
          } else if (data.status === "missing_info") {
            setTranscription(data.event.message);
          }

          if (data.audio) {
            const audioBytes = new Uint8Array(
              data.audio.match(/.{1,2}/g).map((byte: string) => parseInt(byte, 16))
            );
            const audioBlob = new Blob([audioBytes], { type: "audio/wav" });
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            audio.play();
          }
        };

        websocket.onerror = () => {
          setTranscription("WebSocket error. Please try again.");
          setIsRecording(false);
        };

        websocket.onclose = () => {
          setWs(null);
        };
      };

      recorder.start();
      setIsRecording(true);
      setTranscription("Listening...");
    } catch (error) {
      setTranscription(`Error: ${error}`);
      setIsRecording(false);
    }
  } else {
    // Stop recording
    if (mediaRecorder) {
      const stream = mediaRecorder.stream;
      mediaRecorder.stop();

      // 🛑 Stop all tracks (important!)
      stream.getTracks().forEach((track) => track.stop());
    }
    setIsRecording(false);
    setMediaRecorder(null);
  }
};

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
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

            <GoogleLoginButton
              className="bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-all duration-300 shadow-sm hover:shadow-md"
              size="lg" children={undefined}            >
            </GoogleLoginButton>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8">
        <div className="grid lg:grid-cols-3 gap-8">
          {/* Voice Control Panel */}
          <div className="lg:col-span-2 space-y-6">
            {/* Main Voice Interface */}
            <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm hover:shadow-2xl transition-all duration-500">
              <CardHeader className="text-center pb-6">
                <CardTitle className="text-2xl font-semibold text-slate-800">
                  Voice Assistant
                </CardTitle>
                <p className="text-slate-600">
                  Speak naturally to schedule or manage your meetings
                </p>
              </CardHeader>
              <CardContent className="space-y-8">
                {/* Microphone */}
                <div className="flex justify-center">
                  <div className="relative">
                    <Button
                      onClick={toggleRecording}
                      size="lg"
                      className={`w-24 h-24 rounded-full transition-all duration-300 ${
                        isRecording
                          ? "bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 shadow-lg shadow-red-500/25"
                          : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-lg shadow-blue-500/25"
                      } hover:scale-105 active:scale-95`}
                    >
                      {isRecording ? (
                        <MicOff className="w-8 h-8 text-white" />
                      ) : (
                        <Mic className="w-8 h-8 text-white" />
                      )}
                    </Button>

                    {/* Waving Effect */}
                    {isRecording && (
                      <>
                        <div className="absolute inset-0 rounded-full border-4 border-red-400 animate-ping opacity-75"></div>
                        <div className="absolute inset-0 rounded-full border-2 border-red-300 animate-pulse"></div>
                        <div className="absolute -inset-4 rounded-full border border-red-200 animate-ping animation-delay-300"></div>
                      </>
                    )}
                  </div>
                </div>

                {/* Controls */}
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
                    <label className="text-sm font-medium text-slate-700">
                      Status
                    </label>
                    <div
                      className={`px-3 py-2 rounded-md text-sm font-medium transition-all duration-300 ${
                        isRecording
                          ? "bg-red-50 text-red-700 border border-red-200"
                          : "bg-slate-50 text-slate-600 border border-slate-200"
                      }`}
                    >
                      {isRecording ? "Listening..." : "Ready to listen"}
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
              </CardContent>
            </Card>

            {/* Voice Commands Reference */}
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

          {/* Meeting Summary Sidebar */}
          <div className="space-y-6">
            <Card className="border-0 shadow-lg bg-white/70 backdrop-blur-sm hover:shadow-xl transition-all duration-300">
              <CardHeader>
                <CardTitle className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                  <Calendar className="w-5 h-5" />
                  Upcoming Meetings
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px]">
                  <div className="space-y-4">
                    {meetings.map((meeting) => (
                      <div
                        key={meeting.id}
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
                              meeting.status === "scheduled"
                                ? "default"
                                : "destructive"
                            }
                            className={`${
                              meeting.status === "scheduled"
                                ? "bg-green-100 text-green-800 hover:bg-green-200"
                                : "bg-red-100 text-red-800 hover:bg-red-200"
                            } transition-colors`}
                          >
                            {meeting.status === "scheduled" ? (
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
                            {meeting.time}
                          </div>
                          <div className="flex items-center gap-1">
                            <Users className="w-4 h-4" />
                            {meeting.participants}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Quick Stats */}
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
                    <span className="text-slate-600">Canceled Today</span>
                    <span className="font-semibold text-red-600">
                      {meetings.filter((m) => m.status === "canceled").length}
                    </span>
                  </div>
                  <Separator />
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600">Total Participants</span>
                    <span className="font-semibold text-blue-600">
                      {meetings.reduce((acc, m) => acc + m.participants, 0)}
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