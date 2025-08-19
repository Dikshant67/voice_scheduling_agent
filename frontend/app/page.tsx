"use client";
import React, { useState, useRef, useCallback, useEffect } from "react";

// Enhanced interfaces with better type safety
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

interface VoiceAssistantProps {
  websocketUrl?: string;
  timezone?: string;
  enableAdvancedFeatures?: boolean;
  autoReconnect?: boolean;
}

interface ConnectionStats {
  packetsLost: number;
  averageLatency: number;
  audioQuality: number;
  sessionDuration: number;
}

const VoiceAssistant: React.FC<VoiceAssistantProps> = ({
  websocketUrl = "ws://localhost:8000/ws/voice-live",
  timezone = Intl.DateTimeFormat().resolvedOptions().timeZone,
  enableAdvancedFeatures = true,
  autoReconnect = true,
}) => {
  // Enhanced state management
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [messages, setMessages] = useState<string[]>([]);
  const [transcription, setTranscription] = useState<string>("");
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

  // Enhanced refs for real-time audio processing
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<AudioWorkletNode | ScriptProcessorNode | null>(
    null
  );
  const gainNodeRef = useRef<GainNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  // Performance monitoring refs
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const sessionStartTimeRef = useRef<number>(0);
  const lastPingRef = useRef<number>(0);
  const audioChunkCountRef = useRef<number>(0);
  const qualitySamplesRef = useRef<number[]>([]);

  // Audio processing constants - optimized for real-time
  const SAMPLE_RATE = 16000;
  const CHANNELS = 1;
  const BUFFER_SIZE = 1024; // Smaller buffer for lower latency
  const QUALITY_THRESHOLD = 300;
  const MAX_SILENCE_MS = 2000;
  const RECONNECT_DELAY = 3000;

  // Enhanced WebSocket connection with auto-reconnect
  const connectWebSocket = useCallback(() => {
    try {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        console.log("🔗 WebSocket already connected");
        return;
      }

      setConnectionStatus("Connecting...");
      console.log(`🔗 Connecting to: ${websocketUrl}`);

      wsRef.current = new WebSocket(websocketUrl);

      wsRef.current.onopen = () => {
        console.log("✅ WebSocket connected successfully");
        setIsConnected(true);
        setConnectionStatus("Connected");
        sessionStartTimeRef.current = Date.now();
        addMessage("🟢 Connected to enhanced voice assistant");

        // Clear reconnect timeout
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }

        // Start ping mechanism for connection monitoring
        startPingMechanism();
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
        console.log(
          `🔌 WebSocket disconnected: Code ${event.code}, Reason: ${event.reason}`
        );
        setIsConnected(false);
        setConnectionStatus("Disconnected");
        setIsRecording(false);
        setIsProcessing(false);
        addMessage(`🔴 Disconnected (Code: ${event.code})`);

        // Auto-reconnect if enabled and not a clean close
        if (autoReconnect && event.code !== 1000) {
          scheduleReconnect();
        }
      };

      wsRef.current.onerror = (error) => {
        console.error("💥 WebSocket error:", error);
        setConnectionStatus("Connection Error");
        addMessage("❌ Connection error occurred");

        if (autoReconnect) {
          scheduleReconnect();
        }
      };
    } catch (error) {
      console.error("❌ Failed to create WebSocket:", error);
      setConnectionStatus("Failed to Connect");
      if (autoReconnect) {
        scheduleReconnect();
      }
    }
  }, [websocketUrl, autoReconnect]);

  // Auto-reconnect mechanism
  const scheduleReconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) return;

    setConnectionStatus("Reconnecting...");
    addMessage(`🔄 Reconnecting in ${RECONNECT_DELAY / 1000} seconds...`);

    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectTimeoutRef.current = null;
      connectWebSocket();
    }, RECONNECT_DELAY);
  }, [connectWebSocket]);

  // Ping mechanism for connection monitoring
  const startPingMechanism = useCallback(() => {
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        lastPingRef.current = Date.now();
        wsRef.current.send(JSON.stringify({ event: "ping" }));
      } else {
        clearInterval(pingInterval);
      }
    }, 30000); // Ping every 30 seconds

    return () => clearInterval(pingInterval);
  }, []);

  // Enhanced WebSocket message handler
  const handleWebSocketMessage = async (data: AudioMessage) => {
    console.log("📨 Received:", data.type, data.message?.substring(0, 50));

    // Update session ID
    if (data.session_id && !sessionId) {
      setSessionId(data.session_id);
    }

    // Calculate latency for pong responses
    if (data.type === "pong" && lastPingRef.current > 0) {
      const latency = Date.now() - lastPingRef.current;
      setConnectionStats((prev) => ({
        ...prev,
        averageLatency: (prev.averageLatency + latency) / 2,
      }));
    }

    switch (data.type) {
      case "greeting":
        addMessage(data.message || " Enhanced assistant ready");
        if (data.audio) await playAudioFromHex(data.audio);
        break;
      case "processing_error":
        setIsProcessing(false);
        addMessage(`❌ Processing Error: ${data.message}`);
        if (data.audio) await playAudioFromHex(data.audio);
        break;

      case "pong":
        // Handle pong response - just log or update connection stats
        console.log("🏓 Pong received");
        break;
      case "recording_started":
        addMessage("🔴 Recording active...");
        setAudioFeedback(null);
        audioChunkCountRef.current = 0;
        qualitySamplesRef.current = [];
        break;

      case "audio_feedback":
        updateAudioFeedback(data);
        break;

      case "processing_started":
        setIsProcessing(true);
        addMessage(
          `🔄 Processing ${data.audio_duration?.toFixed(1)}s of audio...`
        );
        break;

      case "transcription":
        setTranscription(data.text || "");
        addMessage(
          `💬 You said: "${data.text}" ${
            data.confidence ? `(${data.confidence})` : ""
          }`
        );
        break;

      case "meeting_result":
        setIsProcessing(false);
        addMessage(data.message || "✅ Meeting processed");
        if (data.audio) await playAudioFromHex(data.audio);
        if (data.event_details) {
          console.log("📅 Event details:", data.event_details);
          displayMeetingDetails(data.event_details);
        }
        break;

      case "clarification":
      case "insufficient_audio":
      case "poor_quality":
      case "unclear_speech":
        setIsProcessing(false);
        addMessage(`💭 ${data.message}`);
        if (data.audio) await playAudioFromHex(data.audio);
        break;

      case "goodbye":
        setIsProcessing(false);
        addMessage(data.message || "👋 Goodbye!");
        if (data.audio) await playAudioFromHex(data.audio);
        await stopRecording();
        break;

      case "error":
        setIsProcessing(false);
        addMessage(`❌ Error: ${data.message}`);
        if (data.audio) await playAudioFromHex(data.audio);
        break;

      case "recording_cancelled":
        addMessage("🚫 Recording cancelled");
        setAudioFeedback(null);
        break;

      case "recording_stopped":
        addMessage("⏹️ Recording stopped");
        break;

      default:
        console.log("🤷 Unknown message type:", data.type);
    }
  };

  // Update audio feedback display
  const updateAudioFeedback = (data: AudioMessage) => {
    const feedback: AudioFeedback = {
      chunk_count: data.chunk_count || 0,
      total_bytes: data.total_bytes || 0,
      duration: data.duration || 0,
      quality: data.quality || 0,
      is_silent: data.is_silent || false,
    };

    setAudioFeedback(feedback);

    // Update quality stats
    if (data.quality) {
      qualitySamplesRef.current.push(data.quality);
      if (qualitySamplesRef.current.length > 10) {
        qualitySamplesRef.current.shift();
      }

      const avgQuality =
        qualitySamplesRef.current.reduce((a, b) => a + b, 0) /
        qualitySamplesRef.current.length;
      setConnectionStats((prev) => ({ ...prev, audioQuality: avgQuality }));
    }
  };

  // Display meeting details in UI
  const displayMeetingDetails = (details: any) => {
    if (details.status === "success") {
      addMessage(`📅 Meeting "${details.title}" scheduled successfully!`);
      addMessage(`🕐 Time: ${details.start} - ${details.end}`);
      if (details.attendees) {
        addMessage(`👥 Attendees: ${details.attendees.join(", ")}`);
      }
    }
  };

  // Enhanced audio playback with better error handling
  const playAudioFromHex = async (hexAudio: string): Promise<void> => {
    try {
      const audioData = new Uint8Array(
        hexAudio.match(/.{2}/g)?.map((byte) => parseInt(byte, 16)) || []
      );

      if (audioData.length === 0) {
        console.warn("⚠️ Empty audio data received");
        return;
      }

      // Initialize audio context if needed
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext ||
          (window as any).webkitAudioContext)();
      }

      // Resume audio context if suspended (browser policy)
      if (audioContextRef.current.state === "suspended") {
        await audioContextRef.current.resume();
      }

      try {
        // Try Web Audio API first
        const audioBuffer = await audioContextRef.current.decodeAudioData(
          audioData.buffer.slice(0)
        );
        const source = audioContextRef.current.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContextRef.current.destination);
        source.start();

        console.log(`🔊 Playing audio: ${audioData.length} bytes`);
      } catch (decodeError) {
        console.warn(
          "⚠️ Web Audio decode failed, trying HTML5 Audio:",
          decodeError
        );
        // Fallback to HTML5 Audio
        await playWithHtml5Audio(audioData);
      }
    } catch (error) {
      console.error("🔊 Audio playback failed:", error);
      addMessage("⚠️ Audio playback failed");
    }
  };

  // Fallback HTML5 audio playback
  const playWithHtml5Audio = async (audioData: Uint8Array): Promise<void> => {
    try {
      // const arr = new Uint8Array(audioData);
      const blob = new Blob([audioData], { type: "audio/wav" });
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);

      audio.onended = () => URL.revokeObjectURL(audioUrl);
      audio.onerror = (error) => {
        console.error("HTML5 Audio error:", error);
        URL.revokeObjectURL(audioUrl);
      };

      await audio.play();
    } catch (error) {
      console.error("HTML5 Audio playback failed:", error);
      throw error;
    }
  };

  // Enhanced microphone initialization with better constraints
  const initializeMicrophone = async (): Promise<MediaStream> => {
    try {
      console.log("🎤 Initializing enhanced microphone...");

      // Request microphone with optimal settings
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: CHANNELS,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleSize: 16,
          // googEchoCancellation: true,
          // googAutoGainControl: true,
          // googNoiseSuppression: true,
          // googHighpassFilter: true,
          // googTypingNoiseDetection: true,
        },
      });

      streamRef.current = stream;
      console.log("✅ Microphone initialized successfully");

      // Log stream properties
      const tracks = stream.getAudioTracks();
      if (tracks.length > 0) {
        const settings = tracks[0].getSettings();
        console.log("🎙️ Audio settings:", settings);
        addMessage(
          `🎤 Microphone: ${settings.sampleRate}Hz, ${settings.channelCount}ch`
        );
      }

      return stream;
    } catch (error) {
      console.error("❌ Microphone initialization failed:", error);
      throw new Error(`Microphone access failed: ${error}`);
    }
  };

  // Enhanced real-time recording with optimized processing
  // Enhanced real-time recording with AudioWorkletNode
  const startRecording = async () => {
    if (!isConnected || isRecording) {
      console.warn(
        "⚠️ Cannot start recording: not connected or already recording"
      );
      return;
    }

    try {
      addMessage("🎤 Initializing enhanced recording...");

      const stream = await initializeMicrophone();

      // Initialize or resume audio context
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext ||
          (window as any).webkitAudioContext)({ sampleRate: SAMPLE_RATE });
      }

      if (audioContextRef.current.state === "suspended") {
        await audioContextRef.current.resume();
      }

      // 🎯 ADD THE LINE HERE - Load the audio worklet processor
      try {
        await audioContextRef.current.audioWorklet.addModule(
          "/audio_processor.js"
        );
        console.log("✅ AudioWorklet processor loaded successfully");
      } catch (workletError) {
        console.warn(
          "⚠️ AudioWorklet not supported, falling back to ScriptProcessorNode:",
          workletError
        );
        // Fallback to your existing ScriptProcessorNode code
        return startRecordingWithScriptProcessor(stream);
      }

      // Now create the AudioWorkletNode (this will work because processor is loaded)
      const source = audioContextRef.current.createMediaStreamSource(stream);

      // Create AudioWorkletNode using the loaded processor
      const workletNode = new AudioWorkletNode(
        audioContextRef.current,
        "audio-processor"
      );

      // Handle audio data from worklet
      workletNode.port.onmessage = (event) => {
        if (event.data.type === "audio-data") {
          const pcmData = event.data.data;
          audioChunkCountRef.current++;

          // Send PCM data via WebSocket
          if (
            wsRef.current?.readyState === WebSocket.OPEN &&
            pcmData.byteLength > 0
          ) {
            try {
              wsRef.current.send(pcmData);
              console.log(
                `📡 Sent chunk ${audioChunkCountRef.current}: ${pcmData.byteLength} bytes`
              );
            } catch (sendError) {
              console.error("❌ Failed to send audio data:", sendError);
            }
          }
        }
      };

      // Connect the nodes
      source.connect(workletNode);
      workletNode.connect(audioContextRef.current.destination);

      // Store references for cleanup
      processorRef.current = workletNode as any;
      streamRef.current = stream;

      // Send start recording message
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            event: "start_recording",
            timezone: timezone,
            session_info: {
              browser: navigator.userAgent,
              sample_rate: SAMPLE_RATE,
              buffer_size: 1024,
              audio_api: "AudioWorklet",
            },
          })
        );
      }

      setIsRecording(true);
      setTranscription("");
      addMessage("🔴 Enhanced recording started with AudioWorklet!");
    } catch (error) {
      console.error("❌ Recording start failed:", error);
      addMessage(`❌ Recording failed: ${error}`);
      await cleanupAudioResources();
    }
  };
  const startRecordingWithScriptProcessor = async (stream: MediaStream) => {
    // This is your legacy ScriptProcessorNode code, adapted for fallback use
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext ||
        (window as any).webkitAudioContext)({ sampleRate: SAMPLE_RATE });
    }

    if (audioContextRef.current.state === "suspended") {
      await audioContextRef.current.resume();
    }

    const source = audioContextRef.current.createMediaStreamSource(stream);
    console.log("🎤 Created MediaStreamSource from microphone");

    // Add gain control
    gainNodeRef.current = audioContextRef.current.createGain();
    gainNodeRef.current.gain.value = 1.0;

    // Add analyser for real-time feedback
    analyserRef.current = audioContextRef.current.createAnalyser();
    analyserRef.current.fftSize = 256;
    analyserRef.current.smoothingTimeConstant = 0.3;

    // Create script processor for audio processing
    processorRef.current = audioContextRef.current.createScriptProcessor(
      BUFFER_SIZE,
      CHANNELS,
      CHANNELS
    );

    processorRef.current.onaudioprocess = (e) => {
      if (!isRecording) return;

      const inputData = e.inputBuffer.getChannelData(0);

      const rms = Math.sqrt(
        inputData.reduce((sum, val) => sum + val * val, 0) / inputData.length
      );
      const hasAudio = rms > 0.001;
      if (rms > 0.001) {
        console.log(`🎵 AUDIO: RMS=${rms.toFixed(4)}`);
      }
      // 🎯 ADD THIS DEBUG CHECK
      // const hasAudio = inputData.some((sample) => Math.abs(sample) > 0.001);
      if (hasAudio) {
        console.log(
          `🎵 ScriptProcessor: RMS=${rms.toFixed(4)} - AUDIO DETECTED!`
        );
      } else {
        console.warn(`🔇 ScriptProcessor: RMS=${rms.toFixed(4)} - SILENT`);
      }

      // Convert to 16-bit PCM with enhanced processing
      const pcmData = convertToPCM16Enhanced(inputData);

      // Calculate quality metrics
      const quality = calculateAudioQuality(inputData);
      audioChunkCountRef.current++;

      // Send PCM data via WebSocket
      if (
        wsRef.current?.readyState === WebSocket.OPEN &&
        pcmData.byteLength > 0
      ) {
        try {
          wsRef.current.send(pcmData);
          console.log(
            `📡 Sent chunk ${audioChunkCountRef.current}: ${
              pcmData.byteLength
            } bytes, Quality: ${quality.toFixed(0)}`
          );
        } catch (sendError) {
          console.error("❌ Failed to send audio data:", sendError);
        }
      }
    };

    // Connect audio processing chain
    source.connect(gainNodeRef.current!);
    gainNodeRef.current!.connect(analyserRef.current!);
    analyserRef.current!.connect(processorRef.current!);
    processorRef.current!.connect(audioContextRef.current.destination);

    streamRef.current = stream;

    // Send start recording message
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          event: "start_recording",
          timezone: timezone,
          session_info: {
            browser: navigator.userAgent,
            sample_rate: SAMPLE_RATE,
            buffer_size: BUFFER_SIZE,
            audio_api: "ScriptProcessorNode",
          },
        })
      );
    }

    setIsRecording(true);
    setTranscription("");
    addMessage("🔴 Enhanced recording started! (ScriptProcessorNode fallback)");

    // Start real-time audio monitoring
    startAudioMonitoring();
  };
  // Enhanced PCM conversion with noise reduction
  const convertToPCM16Enhanced = (inputData: Float32Array): ArrayBuffer => {
    const length = inputData.length;
    const result = new Int16Array(length);

    for (let i = 0; i < length; i++) {
      let sample = inputData[i];

      // Apply soft limiting to prevent clipping
      sample = Math.tanh(sample * 0.8);

      // Convert to 16-bit PCM
      const pcmSample = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      result[i] = Math.max(-32768, Math.min(32767, pcmSample));
    }

    return result.buffer;
  };

  // Calculate real-time audio quality metrics
  const calculateAudioQuality = (samples: Float32Array): number => {
    const rms = Math.sqrt(
      samples.reduce((sum, sample) => sum + sample * sample, 0) / samples.length
    );
    return rms * 32768; // Convert to 16-bit scale
  };

  // Real-time audio monitoring for visual feedback
  const startAudioMonitoring = () => {
    if (!analyserRef.current) return;

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);

    const monitor = () => {
      if (!isRecording || !analyserRef.current) return;

      analyserRef.current.getByteFrequencyData(dataArray);

      // Calculate average frequency data for quality indication
      const average =
        dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length;

      // Update connection stats
      setConnectionStats((prev) => ({
        ...prev,
        sessionDuration: (Date.now() - sessionStartTimeRef.current) / 1000,
      }));

      requestAnimationFrame(monitor);
    };

    monitor();
  };

  // Enhanced stop recording with proper cleanup
  const stopRecording = async () => {
    if (!isRecording) return;

    try {
      console.log("⏹️ Stopping enhanced recording...");

      // Send stop message first
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ event: "stop_recording" }));
      }

      await cleanupAudioResources();
      setIsRecording(false);
      setAudioFeedback(null);
      addMessage("⏹️ Recording stopped successfully");
    } catch (error) {
      console.error("❌ Stop recording error:", error);
      addMessage(`⚠️ Stop recording error: ${error}`);
    }
  };

  // Enhanced cancel recording
  const cancelRecording = async () => {
    try {
      console.log("🚫 Cancelling recording...");

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ event: "cancel_recording" }));
      }

      await cleanupAudioResources();
      setIsRecording(false);
      setIsProcessing(false);
      setTranscription("");
      setAudioFeedback(null);
      addMessage("🚫 Recording cancelled");
    } catch (error) {
      console.error("❌ Cancel recording error:", error);
    }
  };

  // Comprehensive audio resource cleanup
  const cleanupAudioResources = async () => {
    try {
      console.log("🧹 Starting enhanced cleanup...");

      // FIRST: Set recording to false to prevent new processing
      setIsRecording(false);

      // SECOND: Handle different processor types
      if (processorRef.current) {
        console.log("🔌 Disconnecting audio processor...");

        // Check if it's an AudioWorkletNode (has port property)
        if ("port" in processorRef.current && processorRef.current.port) {
          console.log("🔌 Cleaning up AudioWorkletNode...");
          processorRef.current.port.onmessage = null;
          processorRef.current.port.close();
        } else if ("onaudioprocess" in processorRef.current) {
          console.log("🔌 Cleaning up ScriptProcessorNode...");
          processorRef.current.onaudioprocess = null;
        }

        processorRef.current.disconnect();
        processorRef.current = null;
      }

      // THIRD: Cleanup other audio nodes
      if (analyserRef.current) {
        analyserRef.current.disconnect();
        analyserRef.current = null;
      }

      if (gainNodeRef.current) {
        gainNodeRef.current.disconnect();
        gainNodeRef.current = null;
      }

      // FOURTH: Stop all media tracks
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => {
          track.stop();
          console.log("🛑 Stopped track:", track.kind);
        });
        streamRef.current = null;
      }

      console.log("🧹 Audio resources cleaned up successfully");
    } catch (error) {
      console.error("❌ Cleanup error:", error);
    }
  };

  // Enhanced message display
  const addMessage = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setMessages((prev) => [...prev.slice(-19), `${timestamp}: ${message}`]); // Keep last 20 messages
  };

  // Disconnect WebSocket
  const disconnect = () => {
    if (wsRef.current) {
      wsRef.current.close(1000, "User initiated disconnect");
      wsRef.current = null;
    }

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  };
  const testMicrophone = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.fftSize);

      const checkAudio = () => {
        analyser.getByteTimeDomainData(dataArray);
        const average =
          dataArray.reduce((sum, value) => sum + Math.abs(value - 128), 0) /
          dataArray.length;
        console.log("🎤 Microphone level:", average);

        if (average > 5) {
          console.log("✅ Microphone is working!");
        } else {
          console.log("❌ Microphone seems silent");
        }
      };

      // Check for 5 seconds
      const interval = setInterval(checkAudio, 500);
      setTimeout(() => {
        clearInterval(interval);
        stream.getTracks().forEach((track) => track.stop());
        audioContext.close();
      }, 5000);
    } catch (error) {
      console.error("❌ Microphone test failed:", error);
    }
  };

  // Enhanced cleanup on unmount
  useEffect(() => {
    return () => {
      console.log("🧹 Component unmounting, cleaning up...");
      cleanupAudioResources();
      disconnect();

      if (
        audioContextRef.current &&
        audioContextRef.current.state !== "closed"
      ) {
        audioContextRef.current.close();
      }
    };
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connectWebSocket();
  }, [connectWebSocket]);

  // Connection quality indicator
  const getConnectionQuality = (): string => {
    if (!isConnected) return "disconnected";
    if (connectionStats.averageLatency > 1000) return "poor";
    if (connectionStats.averageLatency > 500) return "fair";
    return "excellent";
  };

  // Audio quality indicator
  const getAudioQuality = (): string => {
    if (!audioFeedback) return "unknown";
    if (audioFeedback.quality > 1000) return "excellent";
    if (audioFeedback.quality > 500) return "good";
    if (audioFeedback.quality > 200) return "fair";
    return "poor";
  };

  return (
    <div
      className="voice-assistant-container"
      style={{
        padding: "20px",
        maxWidth: "1000px",
        margin: "0 auto",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      <h2
        style={{
          textAlign: "center",
          marginBottom: "30px",
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          fontSize: "2rem",
        }}
      >
        🎤 Enhanced Voice Meeting Assistant
      </h2>
      <button
        onClick={testMicrophone}
        style={{
          backgroundColor: "#4CAF50",
          color: "white",
          border: "none",
          padding: "10px 20px",
          borderRadius: "5px",
          cursor: "pointer",
          marginBottom: "20px",
        }}
      >
        🎤 Test Microphone
      </button>
      {/* Enhanced Connection Status Panel */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "20px",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            background: isConnected ? "#e8f5e8" : "#ffeaa7",
            border: `2px solid ${isConnected ? "#4CAF50" : "#f39c12"}`,
            borderRadius: "10px",
            padding: "15px",
          }}
        >
          <h3 style={{ margin: "0 0 10px 0", fontSize: "1.1rem" }}>
            Connection Status
          </h3>
          <div
            style={{
              fontWeight: "bold",
              fontSize: "1.2rem",
              marginBottom: "5px",
            }}
          >
            {connectionStatus} {isConnected ? "🟢" : "🔴"}
          </div>
          <div style={{ fontSize: "0.9rem", color: "#666" }}>
            Quality: {getConnectionQuality()} | Session:{" "}
            {sessionId.slice(-8) || "N/A"}
          </div>
          {!isConnected && (
            <button
              onClick={connectWebSocket}
              style={{
                marginTop: "10px",
                padding: "8px 16px",
                backgroundColor: "#4CAF50",
                color: "white",
                border: "none",
                borderRadius: "5px",
                cursor: "pointer",
              }}
            >
              🔗 Connect
            </button>
          )}
        </div>

        {/* Real-time Statistics */}
        <div
          style={{
            background: "#f8f9fa",
            border: "2px solid #dee2e6",
            borderRadius: "10px",
            padding: "15px",
          }}
        >
          <h3 style={{ margin: "0 0 10px 0", fontSize: "1.1rem" }}>
            Live Stats
          </h3>
          <div style={{ fontSize: "0.9rem", lineHeight: "1.6" }}>
            <div>
              📊 Latency: {Math.round(connectionStats.averageLatency)}ms
            </div>
            <div>🎵 Audio Quality: {getAudioQuality()}</div>
            <div>
              ⏱️ Session: {Math.round(connectionStats.sessionDuration)}s
            </div>
            <div>📦 Chunks: {audioChunkCountRef.current}</div>
          </div>
        </div>
      </div>

      {/* Enhanced Recording Controls */}
      <div
        style={{
          background: "linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)",
          borderRadius: "15px",
          padding: "20px",
          marginBottom: "20px",
          textAlign: "center",
        }}
      >
        <div style={{ marginBottom: "15px" }}>
          <button
            onClick={startRecording}
            disabled={!isConnected || isRecording || isProcessing}
            style={{
              backgroundColor: isRecording ? "#ff4444" : "#4CAF50",
              color: "white",
              border: "none",
              padding: "15px 30px",
              borderRadius: "25px",
              fontSize: "1.1rem",
              fontWeight: "bold",
              cursor: "pointer",
              marginRight: "15px",
              opacity: !isConnected || isProcessing ? 0.6 : 1,
              transform: isRecording ? "scale(0.95)" : "scale(1)",
              transition: "all 0.2s ease",
            }}
          >
            {isRecording ? "🔴 Recording..." : "🎤 Start Recording"}
          </button>

          <button
            onClick={stopRecording}
            disabled={!isRecording}
            style={{
              backgroundColor: "#008CBA",
              color: "white",
              border: "none",
              padding: "15px 30px",
              borderRadius: "25px",
              fontSize: "1.1rem",
              fontWeight: "bold",
              cursor: "pointer",
              marginRight: "15px",
              opacity: !isRecording ? 0.6 : 1,
            }}
          >
            ⏹️ Stop
          </button>

          <button
            onClick={cancelRecording}
            disabled={!isRecording && !isProcessing}
            style={{
              backgroundColor: "#f44336",
              color: "white",
              border: "none",
              padding: "15px 30px",
              borderRadius: "25px",
              fontSize: "1.1rem",
              fontWeight: "bold",
              cursor: "pointer",
              opacity: !isRecording && !isProcessing ? 0.6 : 1,
            }}
          >
            ❌ Cancel
          </button>
        </div>
        {/* Real-time Audio Feedback */}
        {/* Real-time Audio Feedback */}
        {audioFeedback && isRecording && (
          <div
            style={{
              background: "rgba(255,255,255,0.9)",
              borderRadius: "10px",
              padding: "15px",
              marginTop: "15px",
            }}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
                gap: "10px",
                fontSize: "0.9rem",
              }}
            >
              <div>📊 Chunks: {audioFeedback.chunk_count}</div>
              <div>
                💾 Size: {(audioFeedback.total_bytes / 1024).toFixed(1)} KB
              </div>
              <div>⏱️ Duration: {audioFeedback.duration.toFixed(2)}s</div>
              <div>🎵 Quality: {audioFeedback.quality}</div>
              <div>🔈 Silent: {audioFeedback.is_silent ? "Yes" : "No"}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
export default VoiceAssistant;
