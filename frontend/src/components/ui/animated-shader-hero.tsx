'use client';

import React, { useEffect, useRef } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface AnimatedShaderHeroProps {
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  compact?: boolean;
}

interface ShaderUniverseBackgroundProps {
  className?: string;
  opacity?: number;
  intensity?: number;
  fixed?: boolean;
  fps?: number;
}

type ShaderProgram = WebGLProgram & {
  resolution?: WebGLUniformLocation | null;
  time?: WebGLUniformLocation | null;
  move?: WebGLUniformLocation | null;
  touch?: WebGLUniformLocation | null;
  pointerCount?: WebGLUniformLocation | null;
  pointers?: WebGLUniformLocation | null;
};

class WebGLShaderRenderer {
  private readonly canvas: HTMLCanvasElement;
  private readonly gl: WebGL2RenderingContext;
  private readonly vertexSrc = `#version 300 es
precision highp float;
in vec4 position;
void main(){gl_Position=position;}`;
  private readonly vertices = [-1, 1, -1, -1, 1, 1, 1, -1];
  private shaderSource: string;
  private program: ShaderProgram | null = null;
  private vs: WebGLShader | null = null;
  private fs: WebGLShader | null = null;
  private buffer: WebGLBuffer | null = null;
  private scale: number;

  constructor(canvas: HTMLCanvasElement, scale: number, shaderSource: string) {
    this.canvas = canvas;
    this.scale = scale;
    this.shaderSource = shaderSource;
    const gl = canvas.getContext('webgl2', {
      alpha: true,
      antialias: false,
      depth: false,
      powerPreference: 'low-power',
      premultipliedAlpha: false,
    });

    if (!gl) {
      throw new Error('WebGL2 is not available');
    }

    this.gl = gl;
    this.gl.viewport(0, 0, canvas.width * scale, canvas.height * scale);
  }

  updateScale(scale: number) {
    this.scale = scale;
    this.gl.viewport(0, 0, this.canvas.width * scale, this.canvas.height * scale);
  }

  setup() {
    const gl = this.gl;
    this.vs = gl.createShader(gl.VERTEX_SHADER);
    this.fs = gl.createShader(gl.FRAGMENT_SHADER);

    if (!this.vs || !this.fs) {
      throw new Error('Unable to create shader handles');
    }

    this.compile(this.vs, this.vertexSrc);
    this.compile(this.fs, this.shaderSource);

    const program = gl.createProgram() as ShaderProgram | null;
    if (!program) {
      throw new Error('Unable to create shader program');
    }

    gl.attachShader(program, this.vs);
    gl.attachShader(program, this.fs);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(program) || 'Shader link failed');
    }

    this.program = program;
  }

  init() {
    const gl = this.gl;
    const program = this.program;
    if (!program) return;

    this.buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(this.vertices), gl.STATIC_DRAW);

    const position = gl.getAttribLocation(program, 'position');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

    program.resolution = gl.getUniformLocation(program, 'resolution');
    program.time = gl.getUniformLocation(program, 'time');
    program.move = gl.getUniformLocation(program, 'move');
    program.touch = gl.getUniformLocation(program, 'touch');
    program.pointerCount = gl.getUniformLocation(program, 'pointerCount');
    program.pointers = gl.getUniformLocation(program, 'pointers');
  }

  render(now = 0) {
    const gl = this.gl;
    const program = this.program;
    if (!program || gl.getProgramParameter(program, gl.DELETE_STATUS)) return;

    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(program);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);

    if (program.resolution) gl.uniform2f(program.resolution, this.canvas.width, this.canvas.height);
    if (program.time) gl.uniform1f(program.time, now * 0.001);
    if (program.move) gl.uniform2f(program.move, 0, 0);
    if (program.touch) gl.uniform2f(program.touch, this.canvas.width * 0.5, this.canvas.height * 0.5);
    if (program.pointerCount) gl.uniform1i(program.pointerCount, 0);
    if (program.pointers) gl.uniform2fv(program.pointers, [0, 0]);

    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  destroy() {
    const gl = this.gl;
    if (this.program && !gl.getProgramParameter(this.program, gl.DELETE_STATUS)) {
      if (this.vs) {
        gl.detachShader(this.program, this.vs);
        gl.deleteShader(this.vs);
      }
      if (this.fs) {
        gl.detachShader(this.program, this.fs);
        gl.deleteShader(this.fs);
      }
      gl.deleteProgram(this.program);
    }
    if (this.buffer) {
      gl.deleteBuffer(this.buffer);
    }
  }

  private compile(shader: WebGLShader, source: string) {
    const gl = this.gl;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);

    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      throw new Error(gl.getShaderInfoLog(shader) || 'Shader compilation failed');
    }
  }
}

function useShaderCanvas(reduceMotion: boolean, fps: number) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number | null>(null);
  const rendererRef = useRef<WebGLShaderRenderer | null>(null);
  const visibleRef = useRef(true);
  const lastRenderRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const targetFrameMs = 1000 / Math.max(8, Math.min(30, fps));

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.max(1, Math.min(1.15, window.devicePixelRatio * 0.46));
      canvas.width = Math.max(1, Math.floor((rect.width || window.innerWidth) * dpr));
      canvas.height = Math.max(1, Math.floor((rect.height || window.innerHeight) * dpr));
      rendererRef.current?.updateScale(dpr);
    };

    const renderOnce = (now = 0) => {
      rendererRef.current?.render(now);
    };

    const loop = (now: number) => {
      if (document.visibilityState === 'hidden' || !visibleRef.current) {
        animationFrameRef.current = requestAnimationFrame(loop);
        return;
      }

      if (now - lastRenderRef.current >= targetFrameMs) {
        lastRenderRef.current = now;
        renderOnce(now);
      }
      animationFrameRef.current = requestAnimationFrame(loop);
    };

    try {
      resize();
      rendererRef.current = new WebGLShaderRenderer(canvas, 1, scpaShaderSource);
      rendererRef.current.setup();
      rendererRef.current.init();
      resize();

      if (reduceMotion) {
        renderOnce(0);
      } else {
        animationFrameRef.current = requestAnimationFrame(loop);
      }
    } catch {
      rendererRef.current = null;
    }

    window.addEventListener('resize', resize);
    const observer = new IntersectionObserver(
      ([entry]) => {
        visibleRef.current = Boolean(entry?.isIntersecting);
        if (visibleRef.current) renderOnce(performance.now());
      },
      { rootMargin: '360px' },
    );
    observer.observe(canvas);

    return () => {
      window.removeEventListener('resize', resize);
      observer.disconnect();
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      rendererRef.current?.destroy();
      rendererRef.current = null;
    };
  }, [fps, reduceMotion]);

  return canvasRef;
}

export function ShaderUniverseBackground({
  className = '',
  opacity = 0.55,
  intensity = 1,
  fixed = false,
  fps = 24,
}: ShaderUniverseBackgroundProps) {
  const reduceMotion = useReducedMotion();
  const canvasRef = useShaderCanvas(Boolean(reduceMotion), fps);
  const clampedOpacity = Math.max(0, Math.min(1, opacity));
  const clampedIntensity = Math.max(0.4, Math.min(1.2, intensity));

  return (
    <div
      className={cn('shader-universe-background pointer-events-none inset-0 overflow-hidden', fixed ? 'fixed' : 'absolute', className)}
      style={
        {
          opacity: clampedOpacity,
          '--shader-intensity': clampedIntensity,
        } as React.CSSProperties
      }
      aria-hidden
    >
      <div className="shader-webgl-fallback absolute inset-0" />
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_34%,transparent_0%,rgba(0,0,0,0.18)_42%,rgba(0,0,0,0.72)_100%)]" />
      <div className="shader-noise absolute inset-0" />
    </div>
  );
}

export function AnimatedShaderHero({
  children,
  className = '',
  contentClassName = '',
  compact = false,
}: AnimatedShaderHeroProps) {
  const reducedMotion = useReducedMotion();

  return (
    <div
      className={`animated-shader-hero relative isolate overflow-hidden ${
        compact ? 'min-h-[320px] rounded-[28px]' : 'min-h-screen'
      } ${className}`}
    >
      <ShaderUniverseBackground opacity={compact ? 0.42 : 0.58} />
      <div aria-hidden className="shader-vignette absolute inset-0" />
      <motion.div
        aria-hidden
        className="shader-blob shader-blob-a absolute"
        animate={reducedMotion ? undefined : { x: [0, 24, -12, 0], y: [0, -18, 16, 0] }}
        transition={{ duration: 18, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        aria-hidden
        className="shader-blob shader-blob-b absolute"
        animate={reducedMotion ? undefined : { x: [0, -20, 18, 0], y: [0, 20, -12, 0] }}
        transition={{ duration: 22, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        aria-hidden
        className="shader-blob shader-blob-c absolute"
        animate={reducedMotion ? undefined : { rotate: [0, 18, -10, 0], scale: [1, 1.08, 0.96, 1] }}
        transition={{ duration: 26, repeat: Infinity, ease: 'easeInOut' }}
      />
      <div aria-hidden className="shader-grid-plane absolute inset-0" />
      <div aria-hidden className="shader-noise absolute inset-0" />

      <div className={`relative z-10 flex h-full min-h-[inherit] items-center justify-center ${contentClassName}`}>
        {children}
      </div>
    </div>
  );
}

export const Component = () => (
  <AnimatedShaderHero>
    <div className="text-center text-white">Animated shader surface</div>
  </AnimatedShaderHero>
);

const scpaShaderSource = `#version 300 es
precision highp float;
out vec4 O;
uniform vec2 resolution;
uniform float time;
#define FC gl_FragCoord.xy
#define T time
#define R resolution
#define MN min(R.x,R.y)

float rnd(vec2 p) {
  p=fract(p*vec2(12.9898,78.233));
  p+=dot(p,p+34.56);
  return fract(p.x*p.y);
}

float noise(in vec2 p) {
  vec2 i=floor(p), f=fract(p), u=f*f*(3.-2.*f);
  float a=rnd(i);
  float b=rnd(i+vec2(1,0));
  float c=rnd(i+vec2(0,1));
  float d=rnd(i+1.);
  return mix(mix(a,b,u.x),mix(c,d,u.x),u.y);
}

float fbm(vec2 p) {
  float t=.0, a=1.;
  mat2 m=mat2(1.,-.5,.2,1.2);
  for (int i=0; i<5; i++) {
    t+=a*noise(p);
    p*=2.*m;
    a*=.5;
  }
  return t;
}

float clouds(vec2 p) {
  float d=1., t=.0;
  for (float i=.0; i<3.; i++) {
    float a=d*fbm(i*8.+p.x*.18+.16*(1.+i)*p.y+d+i*i+p);
    t=mix(t,d,a);
    d=a;
    p*=2./(i+1.);
  }
  return t;
}

void main(void) {
  vec2 uv=(FC-.5*R)/MN;
  vec2 st=uv*vec2(1.85,1.05);
  vec3 col=vec3(.004,.010,.024);
  float bg=clouds(vec2(st.x+T*.07,-st.y+T*.035));
  uv*=1.-.18*(sin(T*.12)*.5+.5);

  for (float i=1.; i<12.; i++) {
    uv+=.045*cos(i*vec2(.14+.012*i,.78)+i*i+T*.18+.12*uv.x);
    vec2 p=uv+vec2(sin(T*.06+i)*.04,cos(T*.05+i)*.03);
    float d=length(p);
    vec3 blue=vec3(.04,.23,.95);
    vec3 cyan=vec3(.04,.82,1.);
    vec3 lineColor=mix(blue,cyan,sin(i*1.37)*.5+.5);
    col+=.00165/max(d,.018)*lineColor;
    float b=noise(i+p+bg*1.731);
    col+=.0022*b/length(max(abs(p),vec2(.022+b*.012)))*vec3(.08,.44,.95);
    col=mix(col,vec3(bg*.018,bg*.07,bg*.16),smoothstep(.22,1.2,d));
  }

  float vignette=smoothstep(1.35,.2,length(uv));
  col*=.82+.35*vignette;
  O=vec4(col,1.);
}`;
