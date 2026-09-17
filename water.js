/* ============================================================
   water.js · 实时水波背景（WebGL）
   ------------------------------------------------------------
   画面由两层合成：
     1. 液面层：多层噪声做「域扭曲」，模拟缓慢流动、带漩涡的暗色液体；
        滚动页面时漩涡随之扭转。
     2. 涟漪层：离散二维波动方程。鼠标 / 手指划过时往高度场里注入扰动，
        每帧向四周传播并衰减。高度场存放在半精度浮点纹理里，
        两张纹理交替读写（乒乓渲染）。
   两层法线叠加后做高光着色，其中一盏暖光跟随鼠标，光斑会跟着手走。

   降级策略：
     - 不支持浮点纹理渲染      → 只保留液面层（仍会流动，只是没有涟漪）
     - 不支持 WebGL / 上下文丢失 → 隐藏画布，露出 CSS 渐变兜底
     - 系统开启「减少动态效果」  → 只渲染一帧静态画面
     - 标签页切到后台          → 暂停渲染，不耗电
     - 前几秒帧率偏低          → 自动降低渲染分辨率

   对外暴露 window.WaterFX.drop(x, y, strength, radius)：
   x / y 为视口归一化坐标（0~1，原点左上），供 script.js 在点击等时机溅起水花。
   ============================================================ */
(() => {
  'use strict';

  const canvas = document.getElementById('water');
  if (!canvas) return;

  const root = document.documentElement;
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const coarsePointer = matchMedia('(pointer: coarse)').matches;

  const ctxOptions = {
    alpha: false, antialias: false, depth: false, stencil: false,
    premultipliedAlpha: false, preserveDrawingBuffer: false,
  };
  const gl = canvas.getContext('webgl2', ctxOptions) || canvas.getContext('webgl', ctxOptions);
  if (!gl) { root.classList.add('no-webgl'); return; }
  const isGL2 = typeof WebGL2RenderingContext !== 'undefined' && gl instanceof WebGL2RenderingContext;

  /* ---------- 1. 着色器 ---------- */
  const PRECISION = `
    #ifdef GL_FRAGMENT_PRECISION_HIGH
    precision highp float;
    #else
    precision mediump float;
    #endif
  `;

  // 全屏三角形，vUv 为 0~1 的画面坐标（原点左下）
  const VERT = `
    attribute vec2 aPos;
    varying vec2 vUv;
    void main() {
      vUv = aPos * 0.5 + 0.5;
      gl_Position = vec4(aPos, 0.0, 1.0);
    }
  `;

  // 波动方程一步：R 通道存当前高度，G 通道存上一帧高度
  // next = (上下左右四邻之和) / 2 - 上一帧，再乘阻尼
  const SIM = PRECISION + `
    uniform sampler2D uState;
    uniform vec2 uTexel;
    uniform float uDamping;
    varying vec2 vUv;
    void main() {
      vec4 s = texture2D(uState, vUv);
      float sum = texture2D(uState, vUv + vec2(uTexel.x, 0.0)).r
                + texture2D(uState, vUv - vec2(uTexel.x, 0.0)).r
                + texture2D(uState, vUv + vec2(0.0, uTexel.y)).r
                + texture2D(uState, vUv - vec2(0.0, uTexel.y)).r;
      float next = (sum * 0.5 - s.g) * uDamping;
      gl_FragColor = vec4(next, s.r, 0.0, 1.0);
    }
  `;

  // 注入扰动：沿线段 A→B 叠加一条平滑的「凸起」，A=B 时就是一个点
  const SPLAT = PRECISION + `
    uniform sampler2D uState;
    uniform vec2 uA;
    uniform vec2 uB;
    uniform float uRadius;
    uniform float uStrength;
    uniform float uAspect;
    varying vec2 vUv;
    void main() {
      vec4 s = texture2D(uState, vUv);
      vec2 asp = vec2(uAspect, 1.0);
      vec2 pa = (vUv - uA) * asp;
      vec2 ba = (uB - uA) * asp;
      float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-8), 0.0, 1.0);
      float d = length(pa - ba * h) / uRadius;
      float bump = max(0.0, 1.0 - d * d);
      s.r += uStrength * bump * bump;
      gl_FragColor = s;
    }
  `;

  // 最终着色
  const RENDER = PRECISION + `
    uniform sampler2D uState;
    uniform vec2  uSimTexel;
    uniform float uHasSim;
    uniform vec2  uRes;
    uniform float uTime;
    uniform vec2  uMouse;
    uniform float uScroll;
    uniform float uFade;
    varying vec2  vUv;

    float hash(vec2 p) {
      vec3 p3 = fract(vec3(p.xyx) * 0.1031);
      p3 += dot(p3, p3.yzx + 33.33);
      return fract((p3.x + p3.y) * p3.z);
    }
    float noise(vec2 p) {
      vec2 i = floor(p);
      vec2 f = fract(p);
      vec2 u = f * f * (3.0 - 2.0 * f);
      return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
                 mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
    }
    float fbm(vec2 p) {
      float v = 0.0;
      float a = 0.5;
      mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
      for (int i = 0; i < 4; i++) {
        v += a * noise(p);
        p = m * p;
        a *= 0.5;
      }
      return v;
    }
    // 液面高度：两次域扭曲，让噪声像液体一样被「搅动」
    float liquid(vec2 p) {
      float t = uTime * 0.6;
      vec2 q = vec2(fbm(p + vec2(0.0, t * 0.10)),
                    fbm(p + vec2(5.2, 1.3) - vec2(t * 0.08, 0.0)));
      return fbm(p + 2.8 * q + vec2(t * 0.03, -t * 0.05));
    }

    void main() {
      float aspect = uRes.x / uRes.y;
      vec2 uv = vUv;
      vec2 p = vec2(uv.x * aspect, uv.y);

      // 漩涡：中心在画面右上方，越靠近中心扭得越厉害；滚动页面时继续扭转
      vec2 c = vec2(aspect * 0.66, 0.6);
      vec2 d = p - c;
      float ang = (1.7 + uScroll * 0.35) * exp(-length(d) * 1.8) + uTime * 0.02;
      float cs = cos(ang);
      float sn = sin(ang);
      d = mat2(cs, sn, -sn, cs) * d;
      vec2 q = (c + d) * 1.3 + vec2(0.0, uScroll * 0.12);

      // 液面法线（有限差分）
      float e = 0.015;
      float h0 = liquid(q);
      float hx = liquid(q + vec2(e, 0.0));
      float hy = liquid(q + vec2(0.0, e));
      vec2 grad = vec2(hx - h0, hy - h0) / e;

      // 涟漪法线
      // 隔 1.5 格采样求导：高度场分辨率只有画面的 1/4，逐格求导会让水纹发碎
      vec2 rip = vec2(0.0);
      if (uHasSim > 0.5) {
        vec2 o = uSimTexel * 1.5;
        float l = texture2D(uState, uv - vec2(o.x, 0.0)).r;
        float r = texture2D(uState, uv + vec2(o.x, 0.0)).r;
        float b = texture2D(uState, uv - vec2(0.0, o.y)).r;
        float t = texture2D(uState, uv + vec2(0.0, o.y)).r;
        rip = vec2(r - l, t - b);
      }

      vec3 n = normalize(vec3(-grad * 0.3 - rip * 1.9, 1.0));
      vec3 v = vec3(0.0, 0.0, 1.0);

      // 主光：左上方的冷白面光。宽高光勾出丝绸般的褶皱，窄高光是褶皱脊上的亮线
      vec3 l1 = normalize(vec3(-0.45, 0.55, 0.7));
      float nh1 = max(dot(n, normalize(l1 + v)), 0.0);
      float sheen = pow(nh1, 7.0);
      float glint = pow(nh1, 90.0);
      // 暖光：跟随鼠标，靠近鼠标的水面被照亮
      vec2 toM = (uMouse - uv) * vec2(aspect, 1.0);
      vec3 l2 = normalize(vec3(toM * 1.4, 0.5));
      float nh2 = max(dot(n, normalize(l2 + v)), 0.0);
      float near = exp(-dot(toM, toM) * 7.0);
      // 首屏水面最鲜明；滚进正文区后高光压暗，保证文字可读
      float dim = mix(1.0, 0.4, smoothstep(0.3, 0.95, uScroll));

      vec3 col = vec3(0.011, 0.012, 0.014);
      col += vec3(0.17, 0.175, 0.185) * sheen * sheen * dim;
      col += vec3(0.62, 0.64, 0.68) * glint * 0.4 * dim;
      col += vec3(1.0, 0.70, 0.38) * pow(nh2, 30.0) * near * 0.5 * mix(1.0, dim, 0.75);
      col += vec3(1.0, 0.78, 0.5) * pow(nh2, 6.0) * near * 0.03;
      // 涟漪亮边：不依赖光照方向，保证在哪个位置划水都看得见
      col += vec3(0.78, 0.82, 0.88) * smoothstep(0.004, 0.06, length(rip)) * 0.09;

      // 暗角
      vec2 vc = (uv - 0.5) * vec2(aspect * 0.75, 1.0);
      col *= clamp(1.0 - dot(vc, vc) * 0.9, 0.0, 1.0);
      // 细微颗粒，避免暗部出现色带
      col += (hash(gl_FragCoord.xy + fract(uTime * 3.7) * 400.0) - 0.5) * 0.012;

      gl_FragColor = vec4(max(col, vec3(0.0)) * uFade, 1.0);
    }
  `;

  /* ---------- 2. WebGL 工具 ---------- */
  function compile(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.warn('[water] 着色器编译失败：', gl.getShaderInfoLog(shader));
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  function createProgram(fragmentSource, uniformNames) {
    const vs = compile(gl.VERTEX_SHADER, VERT);
    const fs = compile(gl.FRAGMENT_SHADER, fragmentSource);
    if (!vs || !fs) return null;
    const program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.bindAttribLocation(program, 0, 'aPos');
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.warn('[water] 着色器链接失败：', gl.getProgramInfoLog(program));
      return null;
    }
    const u = {};
    uniformNames.forEach((name) => { u[name] = gl.getUniformLocation(program, name); });
    return { program, u };
  }

  // 半精度浮点纹理的格式；当前环境不支持渲染到浮点纹理时返回 null
  function floatFormat() {
    if (isGL2) {
      if (!gl.getExtension('EXT_color_buffer_float') && !gl.getExtension('EXT_color_buffer_half_float')) return null;
      return { internal: gl.RGBA16F, type: gl.HALF_FLOAT };
    }
    const half = gl.getExtension('OES_texture_half_float');
    if (!half || !gl.getExtension('OES_texture_half_float_linear')) return null;
    gl.getExtension('EXT_color_buffer_half_float');
    return { internal: gl.RGBA, type: half.HALF_FLOAT_OES };
  }

  function createTarget(w, h, fmt) {
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D, 0, fmt.internal, w, h, 0, gl.RGBA, fmt.type, null);

    const fbo = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    const ok = gl.checkFramebufferStatus(gl.FRAMEBUFFER) === gl.FRAMEBUFFER_COMPLETE;
    if (ok) {
      gl.viewport(0, 0, w, h);
      gl.clearColor(0, 0, 0, 1);
      gl.clear(gl.COLOR_BUFFER_BIT);
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    if (!ok) { gl.deleteFramebuffer(fbo); gl.deleteTexture(tex); return null; }
    return { tex, fbo, w, h };
  }

  function deleteTarget(t) {
    if (!t) return;
    gl.deleteFramebuffer(t.fbo);
    gl.deleteTexture(t.tex);
  }

  /* ---------- 3. 初始化 ----------
     所有 GPU 资源都在 setupGL 里创建。显卡上下文丢失（切换显卡、休眠唤醒、
     驱动重置）后浏览器恢复上下文时，会再调用一次把水面重建出来。 */
  let renderProg = null;
  let simProg = null;
  let splatProg = null;
  let fmt = null;
  let hasSim = false;
  let targets = null;   // [读, 写]

  function setupGL() {
    renderProg = createProgram(RENDER, ['uState', 'uSimTexel', 'uHasSim', 'uRes', 'uTime', 'uMouse', 'uScroll', 'uFade']);
    if (!renderProg) return false;

    // 全屏三角形（比两个三角形拼矩形少一条对角线接缝）
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

    fmt = reduceMotion ? null : floatFormat();
    simProg = fmt && createProgram(SIM, ['uState', 'uTexel', 'uDamping']);
    splatProg = fmt && createProgram(SPLAT, ['uState', 'uA', 'uB', 'uRadius', 'uStrength', 'uAspect']);
    hasSim = !!(fmt && simProg && splatProg);
    targets = null;
    return true;
  }
  if (!setupGL()) { root.classList.add('no-webgl'); return; }

  const SIM_STEP = 1 / 60;       // 波动方程固定步长，保证高刷屏上水波速度一致
  const DAMPING = 0.985;         // 每步衰减
  const SIM_MAX_W = 480;         // 高度场最大宽度（格）

  const state = {
    quality: coarsePointer ? 0.4 : 0.55,   // 渲染分辨率 = CSS 像素 × quality
    w: 0, h: 0,
    time: 0,
    fade: 0,
    light:  { x: 0.8, y: 0.82 },           // 暖光位置（平滑后）；鼠标动之前停在右上角，不压正文
    target: { x: 0.8, y: 0.82 },
    lastPointer: null,                      // 上一帧已注入的指针位置
    pendingPointer: null,                   // 本帧最新指针位置
    scroll: 0, scrollTarget: 0,
    drops: [],
    ambientIn: 2,
  };

  function resize(force) {
    if (gl.isContextLost()) return;
    const cw = window.innerWidth;
    const ch = window.innerHeight;
    const w = Math.max(2, Math.round(cw * state.quality));
    const h = Math.max(2, Math.round(ch * state.quality));
    // 手机地址栏伸缩只改变少量高度，这种情况不重建缓冲区，交给 CSS 拉伸
    if (!force && w === state.w && state.h && Math.abs(h - state.h) < state.h * 0.2) return;
    state.w = canvas.width = w;
    state.h = canvas.height = h;

    if (hasSim) {
      const simW = Math.min(SIM_MAX_W, Math.round(cw * 0.25));
      const simH = Math.max(16, Math.round(simW * ch / cw));
      if (!targets || targets[0].w !== simW || targets[0].h !== simH) {
        if (targets) targets.forEach(deleteTarget);
        const a = createTarget(simW, simH, fmt);
        const b = a && createTarget(simW, simH, fmt);
        if (a && b) {
          targets = [a, b];
        } else {
          deleteTarget(a);
          targets = null;
          hasSim = false;   // 浮点渲染实际不可用，退回纯液面
        }
      }
    }
  }

  function toUv(clientX, clientY) {
    return { x: clientX / window.innerWidth, y: 1 - clientY / window.innerHeight };
  }

  /* ---------- 4. 模拟与渲染 ---------- */
  function bindDraw(prog, target) {
    gl.bindFramebuffer(gl.FRAMEBUFFER, target ? target.fbo : null);
    gl.viewport(0, 0, target ? target.w : state.w, target ? target.h : state.h);
    gl.useProgram(prog.program);
  }

  function stepSim() {
    const [src, dst] = targets;
    bindDraw(simProg, dst);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, src.tex);
    gl.uniform1i(simProg.u.uState, 0);
    gl.uniform2f(simProg.u.uTexel, 1 / src.w, 1 / src.h);
    gl.uniform1f(simProg.u.uDamping, DAMPING);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    targets.reverse();
  }

  function splat(ax, ay, bx, by, radius, strength) {
    const [src, dst] = targets;
    bindDraw(splatProg, dst);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, src.tex);
    const u = splatProg.u;
    gl.uniform1i(u.uState, 0);
    gl.uniform2f(u.uA, ax, ay);
    gl.uniform2f(u.uB, bx, by);
    gl.uniform1f(u.uRadius, radius);
    gl.uniform1f(u.uStrength, strength);
    gl.uniform1f(u.uAspect, window.innerWidth / window.innerHeight);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    targets.reverse();
  }

  function render() {
    bindDraw(renderProg, null);
    const u = renderProg.u;
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, hasSim ? targets[0].tex : null);
    gl.uniform1i(u.uState, 0);
    gl.uniform2f(u.uSimTexel, hasSim ? 1 / targets[0].w : 0, hasSim ? 1 / targets[0].h : 0);
    gl.uniform1f(u.uHasSim, hasSim ? 1 : 0);
    gl.uniform2f(u.uRes, state.w, state.h);
    gl.uniform1f(u.uTime, state.time);
    gl.uniform2f(u.uMouse, state.light.x, state.light.y);
    gl.uniform1f(u.uScroll, state.scroll);
    gl.uniform1f(u.uFade, state.fade);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  function simulate(dt) {
    // 1) 指针拖尾：把上一帧到这一帧的移动轨迹作为一条线段注入
    const p = state.pendingPointer;
    if (p) {
      const last = state.lastPointer;
      if (last) {
        const aspect = window.innerWidth / window.innerHeight;
        const dist = Math.hypot((p.x - last.x) * aspect, p.y - last.y);
        // 距离过大说明指针是从窗口外进来的，不画长拖尾
        if (dist > 0.0006 && dist < 0.2) splat(last.x, last.y, p.x, p.y, 0.028, Math.min(0.4, dist * 3.5));
      }
      state.lastPointer = p;
      state.pendingPointer = null;
    }

    // 2) 环境水滴：没人操作时水面也有零星涟漪
    state.ambientIn -= dt;
    if (state.ambientIn <= 0) {
      state.drops.push({
        x: 0.08 + Math.random() * 0.84,
        y: 0.08 + Math.random() * 0.84,
        r: 0.012 + Math.random() * 0.012,
        s: (Math.random() < 0.5 ? -1 : 1) * (0.3 + Math.random() * 0.3),
      });
      state.ambientIn = 1.4 + Math.random() * 2.6;
    }

    // 3) 点状水花（点击、脚本调用、环境水滴）
    while (state.drops.length) {
      const d = state.drops.shift();
      splat(d.x, d.y, d.x, d.y, d.r, d.s);
    }

    // 4) 按固定步长推进波动方程
    simAcc += dt;
    let steps = 0;
    while (simAcc >= SIM_STEP && steps < 3) {
      stepSim();
      simAcc -= SIM_STEP;
      steps++;
    }
    if (steps === 3) simAcc = 0;
  }

  let raf = 0;
  let lastNow = 0;
  let simAcc = 0;
  const perf = { frames: 0, time: 0, checks: 0 };

  function frame(now) {
    raf = requestAnimationFrame(frame);
    const dt = lastNow ? Math.min(0.05, (now - lastNow) / 1000) : SIM_STEP;
    lastNow = now;

    state.time += dt;
    state.fade = Math.min(1, state.fade + dt / 1.8);
    const k = 1 - Math.exp(-dt * 4);
    state.light.x += (state.target.x - state.light.x) * k;
    state.light.y += (state.target.y - state.light.y) * k;
    state.scroll += (state.scrollTarget - state.scroll) * (1 - Math.exp(-dt * 3));

    if (hasSim) simulate(dt);
    render();

    // 自适应画质：加载 2 秒后开始统计，平均帧率低于 45 就降低分辨率（最多两次）
    if (state.time > 2 && perf.checks < 2) {
      perf.frames++;
      perf.time += dt;
      if (perf.frames === 90) {
        if (perf.time / perf.frames > 1 / 45 && state.quality > 0.3) {
          state.quality = Math.max(0.3, state.quality * 0.72);
          resize(true);
        }
        perf.frames = 0;
        perf.time = 0;
        perf.checks++;
      }
    }
  }

  function start() {
    if (raf) return;
    lastNow = 0;
    raf = requestAnimationFrame(frame);
  }
  function stop() {
    cancelAnimationFrame(raf);
    raf = 0;
  }

  /* ---------- 5. 事件 ---------- */
  resize(true);
  canvas.classList.add('is-ready');

  // 上下文丢失：先停下，露出 CSS 兜底背景；浏览器恢复上下文后重建资源继续渲染
  canvas.addEventListener('webglcontextlost', (e) => {
    e.preventDefault();   // 声明「会自己处理恢复」，浏览器才会触发 webglcontextrestored
    stop();
    targets = null;
    canvas.classList.remove('is-ready');
  });
  canvas.addEventListener('webglcontextrestored', () => {
    if (!setupGL()) { root.classList.add('no-webgl'); return; }
    state.w = 0;
    resize(true);
    canvas.classList.add('is-ready');
    if (reduceMotion) render();
    else if (!document.hidden) start();
  });

  if (reduceMotion) {
    // 只画一帧静态液面
    state.time = 18;
    state.fade = 1;
    render();
    window.addEventListener('resize', () => { resize(true); render(); });
    window.WaterFX = { drop() {} };
    return;
  }

  window.addEventListener('resize', () => resize(false));

  window.addEventListener('pointermove', (e) => {
    const p = toUv(e.clientX, e.clientY);
    state.target.x = p.x;
    state.target.y = p.y;
    state.pendingPointer = p;
  }, { passive: true });

  // 手指滑动页面时 pointermove 会被浏览器接管，改用 touchmove 继续拨动水面
  window.addEventListener('touchmove', (e) => {
    const t = e.touches[0];
    if (!t) return;
    const p = toUv(t.clientX, t.clientY);
    state.target.x = p.x;
    state.target.y = p.y;
    state.pendingPointer = p;
  }, { passive: true });

  window.addEventListener('pointerdown', (e) => {
    const p = toUv(e.clientX, e.clientY);
    state.drops.push({ x: p.x, y: p.y, r: 0.04, s: -1.1 });
  }, { passive: true });

  // 指针离开窗口：下次进入时不要从旧位置拉出一条长拖尾
  document.documentElement.addEventListener('mouseleave', () => { state.lastPointer = null; });

  window.addEventListener('scroll', () => {
    state.scrollTarget = window.scrollY / Math.max(1, window.innerHeight);
  }, { passive: true });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stop();
    else if (!gl.isContextLost()) start();
  });

  window.WaterFX = {
    drop(x, y, strength = -1, radius = 0.04) {
      if (hasSim) state.drops.push({ x, y: 1 - y, r: radius, s: strength });
    },
  };

  start();
})();
