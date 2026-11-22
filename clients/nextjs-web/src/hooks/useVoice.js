import { useEffect, useRef } from "react";
import { newVoiceState, nextAnnouncement } from "../logic";

let audioCtx = null;

/** Short beep (slide 34 "Beep"), played before a spoken orange warning. */
export function beep(volume = 0.8) {
  try {
    audioCtx ??= new AudioContext();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.frequency.value = 880;
    gain.gain.value = 0.25 * volume;
    osc.connect(gain).connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.15);
  } catch {
    /* audio not available */
  }
}

/**
 * Speak each new orange warning once (browser speech API). Calm rules live in
 * `nextAnnouncement`: no repeats within voice_repeat_s, one sentence per voice_gap_s,
 * and a sentence is never cut off by the next one.
 */
export function useVoice(warnings, settings) {
  const state = useRef(newVoiceState());
  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;
    const busy = synth.speaking || synth.pending;
    const sentence = nextAnnouncement(state.current, warnings, settings, performance.now(), busy);
    if (!sentence) return;
    const volume = settings?.volume ?? 0.85;
    if (settings?.beep ?? true) beep(volume);
    const u = new SpeechSynthesisUtterance(sentence);
    u.volume = volume;
    u.rate = settings?.speech_speed ?? 1;
    synth.speak(u);
  }, [warnings, settings]);
}

/** Call from a click handler: browsers only allow speech and sound after a user gesture. */
export function unlockSpeech(text = "Driving assistant started") {
  if (!("speechSynthesis" in window)) return;
  try {
    audioCtx ??= new AudioContext();
    void audioCtx.resume();
  } catch {
    /* ignore */
  }
  const u = new SpeechSynthesisUtterance(text);
  u.volume = 0.6;
  window.speechSynthesis.speak(u);
}
