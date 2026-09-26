/* Microphone capture -> 16 kHz mono 16-bit WAV, encoded in the browser.
   No MediaRecorder/opus, no ffmpeg, no server-side decode: what we POST is
   exactly what the ASR engines want, which keeps the voice flow to a
   single API request per utterance (the 35/min budget is precious).

   WSL2 note: the Linux side has no audio devices, but the browser on
   Windows does - getUserMedia works fine against the WSL-served page. */

export class WavRecorder {
  constructor() {
    this.ctx = null;
    this.stream = null;
    this.node = null;
    this.chunks = [];
    this.recording = false;
  }

  async start() {
    if (this.recording) return;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    // ScriptProcessor is deprecated but universally available and perfectly
    // fine for push-to-talk; AudioWorklet would need a second module file
    // and buys us nothing at demo scale.
    this.node = this.ctx.createScriptProcessor(4096, 1, 1);
    this.chunks = [];
    const source = this.ctx.createMediaStreamSource(this.stream);
    source.connect(this.node);
    this.node.connect(this.ctx.destination);
    this.node.onaudioprocess = (e) => {
      if (this.recording) this.chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    };
    this.recording = true;
  }

  async stop() {
    if (!this.recording) return null;
    this.recording = false;
    // Give the last audio block a beat to land, then tear everything down.
    await new Promise((r) => setTimeout(r, 220));
    const wav = encodeWav(this.chunks, this.ctx.sampleRate);
    this.node.disconnect();
    this.stream.getTracks().forEach((t) => t.stop());
    this.ctx.close();
    this.node = this.stream = this.ctx = null;
    return wav;
  }

  static get supported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia &&
      (window.AudioContext || window.webkitAudioContext));
  }
}

function encodeWav(chunks, srcRate) {
  const target = 16000;
  // Concatenate captured Float32 buffers.
  let total = 0;
  for (const c of chunks) total += c.length;
  const merged = new Float32Array(total);
  let off = 0;
  for (const c of chunks) { merged.set(c, off); off += c.length; }

  // Linear resample to 16 kHz (same approach as the backend helper).
  const outLen = Math.max(1, Math.floor(merged.length * target / srcRate));
  const pcm = new Int16Array(outLen);
  const step = srcRate / target;
  let pos = 0;
  for (let i = 0; i < outLen; i++) {
    const idx = Math.floor(pos);
    const frac = pos - idx;
    const s = merged[idx] * (1 - frac) + (merged[idx + 1] ?? merged[idx]) * frac;
    pcm[i] = Math.max(-1, Math.min(1, s)) * 32767;
    pos += step;
  }

  // RIFF header.
  const buf = new ArrayBuffer(44 + pcm.length * 2);
  const view = new DataView(buf);
  const w = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  w(0, "RIFF"); view.setUint32(4, 36 + pcm.length * 2, true); w(8, "WAVE");
  w(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, target, true);
  view.setUint32(28, target * 2, true); view.setUint16(32, 2, true);
  view.setUint16(34, 16, true); w(36, "data"); view.setUint32(40, pcm.length * 2, true);
  new Int16Array(buf, 44).set(pcm);

  return new Blob([buf], { type: "audio/wav" });
}

/* Play a base64 WAV returned by the TTS stage. Returns a stoppable element. */
export function playB64(b64) {
  const bytes = atob(b64);
  const buf = new ArrayBuffer(bytes.length);
  const arr = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([buf], { type: "audio/wav" }));
  const audio = new Audio(url);
  audio.play();
  audio.addEventListener("ended", () => URL.revokeObjectURL(url));
  return audio;
}
