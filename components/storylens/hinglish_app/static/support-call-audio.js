class StorylensVoiceCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.chunkLength = Math.round(sampleRate * 0.032);
    this.chunk = new Float32Array(this.chunkLength);
    this.offset = 0;
  }

  process(inputs) {
    const mono = inputs[0]?.[0];
    if (!mono) return true;
    let start = 0;
    while (start < mono.length) {
      const count = Math.min(mono.length - start, this.chunkLength - this.offset);
      this.chunk.set(mono.subarray(start, start + count), this.offset);
      start += count;
      this.offset += count;
      if (this.offset === this.chunkLength) {
        this.port.postMessage(this.chunk, [this.chunk.buffer]);
        this.chunk = new Float32Array(this.chunkLength);
        this.offset = 0;
      }
    }
    return true;
  }
}

registerProcessor('storylens-voice-capture', StorylensVoiceCapture);
