'use client';

import { useEffect, useRef } from 'react';

import { cn } from '@/lib/utils';

const IMAGE = '/textures/caustics.jpg';
// Ripples alive at once. Must match the array size in the shader.
const MAX_RIPPLES = 10;
const RIPPLE_LIFE_S = 2.4;
// The pointer has to travel this far (as a share of the width) to drop another ripple.
const RIPPLE_SPACING = 0.035;
const MAX_PIXEL_RATIO = 1.5;

const VERTEX = `
attribute vec2 position;
varying vec2 vUv;
void main() {
  vUv = position * 0.5 + 0.5;
  gl_Position = vec4(position, 0.0, 1.0);
}`;

// The picture is drawn through a surface that bends it: a slow swell all the
// time, plus a ring spreading out from each place the pointer has been.
const FRAGMENT = `
precision mediump float;
uniform sampler2D uImage;
uniform vec2 uSize;
uniform vec2 uImageSize;
uniform float uTime;
uniform vec3 uRipples[${MAX_RIPPLES}];
varying vec2 vUv;

vec2 cover(vec2 uv) {
  float box = uSize.x / uSize.y;
  float image = uImageSize.x / uImageSize.y;
  vec2 scale = box > image ? vec2(1.0, image / box) : vec2(box / image, 1.0);
  // Zoomed in a touch, so bending the picture never shows its edge.
  return (uv - 0.5) * scale * 0.94 + 0.5;
}

void main() {
  vec2 aspect = vec2(uSize.x / uSize.y, 1.0);
  vec2 bend = vec2(
    sin(vUv.y * 7.0 + uTime * 0.45) + sin(vUv.x * 4.0 - uTime * 0.3),
    cos(vUv.x * 6.0 - uTime * 0.4) + cos(vUv.y * 5.0 + uTime * 0.25)
  ) * 0.004;

  float glint = 0.0;
  for (int i = 0; i < ${MAX_RIPPLES}; i++) {
    float age = uRipples[i].z;
    if (age < 0.0) continue;
    vec2 away = (vUv - uRipples[i].xy) * aspect;
    float distance = length(away);
    float ring = distance - age * 0.22;
    float fade = exp(-age * 1.7) * exp(-ring * ring * 90.0);
    float wave = sin(ring * 46.0) * fade;
    bend += normalize(away + 0.0001) * wave * 0.03;
    glint += abs(wave);
  }

  vec3 colour = texture2D(uImage, cover(vUv + bend)).rgb;
  gl_FragColor = vec4(colour * (1.0 + glint * 0.7), 1.0);
}`;

function compile(gl: WebGLRenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null;
}

/**
 * The caustics texture as moving water: it swells slowly on its own and ripples
 * where the pointer passes over the panel it sits in.
 *
 * It starts as the same still image Texture shows, and stays that way when
 * WebGL is missing or the visitor asks for reduced motion. Drawing stops while
 * it is off screen.
 */
export function LiquidTexture({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const panel = canvas?.parentElement;
    if (!canvas || !panel) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const gl = canvas.getContext('webgl', { antialias: false, alpha: false });
    const vertex = gl && compile(gl, gl.VERTEX_SHADER, VERTEX);
    const fragment = gl && compile(gl, gl.FRAGMENT_SHADER, FRAGMENT);
    const program = gl?.createProgram();
    if (!gl || !vertex || !fragment || !program) return;
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);

    // Two triangles covering the whole canvas.
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );
    const position = gl.getAttribLocation(program, 'position');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

    const uniform = (name: string) => gl.getUniformLocation(program, name);
    const uSize = uniform('uSize');
    const uImageSize = uniform('uImageSize');
    const uTime = uniform('uTime');
    const uRipples = uniform('uRipples');

    // Each ripple is x, y and the time it started (negative: unused).
    const ripples = Array.from({ length: MAX_RIPPLES }, () => ({ x: 0, y: 0, born: -1 }));
    const packed = new Float32Array(MAX_RIPPLES * 3);
    let next = 0;
    let last = { x: -1, y: -1 };
    let frame = 0;
    let ready = false;
    let visible = false;
    const seconds = () => performance.now() / 1000;

    const image = new Image();
    image.onload = () => {
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
      gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, image);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.uniform2f(uImageSize, image.naturalWidth, image.naturalHeight);
      ready = true;
      start();
    };
    image.src = IMAGE;

    function resize() {
      const ratio = Math.min(window.devicePixelRatio, MAX_PIXEL_RATIO);
      canvas!.width = Math.round(canvas!.clientWidth * ratio);
      canvas!.height = Math.round(canvas!.clientHeight * ratio);
      gl!.viewport(0, 0, canvas!.width, canvas!.height);
      gl!.uniform2f(uSize, canvas!.width, canvas!.height);
    }

    function draw() {
      const now = seconds();
      ripples.forEach((ripple, index) => {
        const age = ripple.born < 0 ? -1 : now - ripple.born;
        packed[index * 3] = ripple.x;
        packed[index * 3 + 1] = ripple.y;
        packed[index * 3 + 2] = age > RIPPLE_LIFE_S ? -1 : age;
      });
      gl!.uniform3fv(uRipples, packed);
      gl!.uniform1f(uTime, now);
      gl!.drawArrays(gl!.TRIANGLES, 0, 6);
      frame = requestAnimationFrame(draw);
    }

    function start() {
      cancelAnimationFrame(frame);
      if (ready && visible && !document.hidden) frame = requestAnimationFrame(draw);
    }

    function onPointerMove(event: PointerEvent) {
      const box = canvas!.getBoundingClientRect();
      const x = (event.clientX - box.left) / box.width;
      const y = 1 - (event.clientY - box.top) / box.height;
      if (Math.hypot(x - last.x, y - last.y) < RIPPLE_SPACING) return;
      last = { x, y };
      ripples[next] = { x, y, born: seconds() };
      next = (next + 1) % MAX_RIPPLES;
    }

    const sizes = new ResizeObserver(resize);
    sizes.observe(canvas);
    const sight = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? false;
      start();
    });
    sight.observe(canvas);
    document.addEventListener('visibilitychange', start);
    // The canvas sits behind the panel's content, so the panel hears the pointer.
    panel.addEventListener('pointermove', onPointerMove, { passive: true });

    return () => {
      cancelAnimationFrame(frame);
      sizes.disconnect();
      sight.disconnect();
      document.removeEventListener('visibilitychange', start);
      panel.removeEventListener('pointermove', onPointerMove);
      image.onload = null;
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 size-full bg-[url('/textures/caustics.jpg')] bg-cover bg-center mix-blend-screen",
        className,
      )}
    />
  );
}
