// public/audio_processor.js
class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 1024;
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs;

    // Critical: Check if we have input channels
    if (input && input.length > 0 && input) {
      const inputChannel = input;

      // Debug: Log non-zero samples
      const hasAudio = inputChannel.some((sample) => Math.abs(sample) > 0.001);
      if (hasAudio) {
        console.log("🎵 AudioWorklet: Detected real audio!");
      }

      for (let i = 0; i < inputChannel.length; i++) {
        this.buffer[this.bufferIndex] = inputChannel[i];
        this.bufferIndex++;

        if (this.bufferIndex >= this.bufferSize) {
          const pcmData = this.convertToPCM16(this.buffer);

          this.port.postMessage({
            type: "audio-data",
            data: pcmData,
          });

          this.bufferIndex = 0;
        }
      }
    } else {
      // Critical: Log when no input is available
      console.warn("🔇 AudioWorklet: No input channels available!");
    }

    return true;
  }

  convertToPCM16(samples) {
    const buffer = new ArrayBuffer(samples.length * 2);
    const view = new DataView(buffer);

    for (let i = 0; i < samples.length; i++) {
      let sample = Math.max(-1, Math.min(1, samples[i]));
      sample = Math.tanh(sample * 0.8);
      sample = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      view.setInt16(i * 2, sample, true);
    }

    return buffer;
  }
}

registerProcessor("audio-processor", AudioProcessor);
