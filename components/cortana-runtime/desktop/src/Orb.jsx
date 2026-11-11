import { useEffect, useRef } from "react";

// Jarvis/Her-style reactive particle sphere. Pure 2D canvas (no WebGL) —
// this laptop's GPU (GTX 1650 4GB) is already earmarked for the LLM, so
// the UI shouldn't compete for VRAM. A few hundred points redrawn with
// canvas 2D easily holds 60fps on integrated-tier hardware.
//
// `state` drives motion — including a deliberately dramatic size change,
// not just color/speed, so it reads at a glance whether Cortana is
// listening to you:
//   idle     - small, slow, calm breathing rotation
//   listening- visibly larger + brighter + faster jitter (you're talking)
//   thinking - contracted, fast rotation (processing)
//   speaking - mid-size, rhythmic pulse driven by the TTS audio's real
//              amplitude when `analyser` is provided, else a synthetic pulse
const POINT_COUNT = 260;

// radiusScale is the whole point of this table: listening is ~3x idle so
// there is never any doubt about whether Cortana is hearing you.
const STATE_STYLE = {
  idle: { speed: 0.15, jitter: 0.02, radiusScale: 0.5, glow: 0.45, color: [56, 214, 214] },
  listening: { speed: 0.5, jitter: 0.16, radiusScale: 1.55, glow: 1, color: [64, 230, 255] },
  thinking: { speed: 1.3, jitter: 0.06, radiusScale: 0.72, glow: 0.7, color: [120, 190, 255] },
  speaking: { speed: 0.5, jitter: 0.04, radiusScale: 1.1, glow: 1, color: [80, 255, 220] },
};

// How fast the orb eases toward the target size for the current state.
// Snappier when growing than shrinking: the jump to "listening" should
// feel instant (it's feedback that you were heard), while settling back
// down can be relaxed.
const SIZE_EASE_UP = 0.22;
const SIZE_EASE_DOWN = 0.06;

function makeSpherePoints(count) {
  // Fibonacci sphere — even point distribution without clustering at poles.
  const points = [];
  const phi = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2;
    const radiusAtY = Math.sqrt(1 - y * y);
    const theta = phi * i;
    points.push({
      x: Math.cos(theta) * radiusAtY,
      y,
      z: Math.sin(theta) * radiusAtY,
    });
  }
  return points;
}

export default function Orb({ state = "idle", analyser = null, size = 320 }) {
  const canvasRef = useRef(null);
  const pointsRef = useRef(makeSpherePoints(POINT_COUNT));
  const rotationRef = useRef({ x: 0, y: 0 });
  const stateRef = useRef(state);
  const analyserRef = useRef(analyser);
  const audioLevelRef = useRef(0);
  const radiusScaleRef = useRef(STATE_STYLE.idle.radiusScale);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    analyserRef.current = analyser;
  }, [analyser]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const freqData = new Uint8Array(64);
    let raf;

    function frame(t) {
      const style = STATE_STYLE[stateRef.current] || STATE_STYLE.idle;
      const cx = size / 2;
      const cy = size / 2;
      // Kept modest on purpose: radiusScale swings from 0.5 (idle) to 1.55
      // (listening) — a >3x change — and the glow extends past the point
      // sphere, so this keeps the largest state inside the canvas instead
      // of clipping at the edges.
      const baseRadius = size * 0.185;

      const target = style.radiusScale;
      const ease = target > radiusScaleRef.current ? SIZE_EASE_UP : SIZE_EASE_DOWN;
      radiusScaleRef.current += (target - radiusScaleRef.current) * ease;

      // Real amplitude from the TTS audio when speaking, else a gentle
      // synthetic breathing pulse so the orb never looks fully static.
      let level = 0.15 * Math.sin(t / 600) + 0.15;
      const reactive = stateRef.current === "speaking" || stateRef.current === "listening";
      if (reactive && analyserRef.current) {
        analyserRef.current.getByteFrequencyData(freqData);
        const avg = freqData.reduce((a, b) => a + b, 0) / freqData.length;
        // Mic input is quieter than TTS playback, so give "listening" more
        // gain — the orb should visibly swell as you talk.
        const gain = stateRef.current === "listening" ? 2.2 : 1;
        level = Math.min(1, (avg / 255) * gain);
      }
      audioLevelRef.current += (level - audioLevelRef.current) * 0.25;

      ctx.clearRect(0, 0, size, size);

      rotationRef.current.y += 0.004 * style.speed;
      rotationRef.current.x += 0.0016 * style.speed;
      const { x: rx, y: ry } = rotationRef.current;
      const cosY = Math.cos(ry), sinY = Math.sin(ry);
      const cosX = Math.cos(rx), sinX = Math.sin(rx);

      const radius = baseRadius * radiusScaleRef.current * (1 + audioLevelRef.current * 0.35);
      const [r, g, b] = style.color;

      // Outer glow
      const glowGrad = ctx.createRadialGradient(cx, cy, radius * 0.2, cx, cy, radius * 1.6);
      glowGrad.addColorStop(0, `rgba(${r},${g},${b},${0.18 * style.glow})`);
      glowGrad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = glowGrad;
      ctx.fillRect(0, 0, size, size);

      const projected = pointsRef.current.map((p) => {
        // rotate around Y then X
        let x = p.x * cosY - p.z * sinY;
        let z = p.x * sinY + p.z * cosY;
        let y = p.y * cosX - z * sinX;
        z = p.y * sinX + z * cosX;

        const jitter = style.jitter * Math.sin(t / 180 + p.x * 10);
        const depth = (z + 1.4) / 2.4; // 0..~1, used for size/alpha falloff
        return {
          sx: cx + x * radius * (1 + jitter * 0.1),
          sy: cy + y * radius * (1 + jitter * 0.1),
          depth,
        };
      });

      // Faint connective lines between near neighbours — the "network" feel.
      ctx.lineWidth = 0.5;
      for (let i = 0; i < projected.length; i += 1) {
        const a = projected[i];
        if (a.depth < 0.35) continue;
        const bpt = projected[(i + 7) % projected.length];
        if (bpt.depth < 0.35) continue;
        const dist = Math.hypot(a.sx - bpt.sx, a.sy - bpt.sy);
        if (dist < radius * 0.55) {
          ctx.strokeStyle = `rgba(${r},${g},${b},${0.12 * a.depth * style.glow})`;
          ctx.beginPath();
          ctx.moveTo(a.sx, a.sy);
          ctx.lineTo(bpt.sx, bpt.sy);
          ctx.stroke();
        }
      }

      // Points, back-to-front so front ones draw on top.
      projected
        .sort((a, b) => a.depth - b.depth)
        .forEach((p) => {
          const alpha = (0.25 + p.depth * 0.75) * style.glow;
          const r2 = 0.9 + p.depth * 1.6;
          ctx.beginPath();
          ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`;
          ctx.arc(p.sx, p.sy, r2, 0, Math.PI * 2);
          ctx.fill();
        });

      // Core glow
      const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius * 0.3);
      coreGrad.addColorStop(0, `rgba(${r},${g},${b},${0.5 * style.glow})`);
      coreGrad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = coreGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, radius * 0.3, 0, Math.PI * 2);
      ctx.fill();

      raf = requestAnimationFrame(frame);
    }

    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [size]);

  return <canvas ref={canvasRef} style={{ width: size, height: size }} />;
}
