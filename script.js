/* ============================================================
   script.js · 伍梓侨 个人简历 v2 · 交互脚本
   ------------------------------------------------------------
   1. 工具与环境探测
   2. 自定义光标
   3. 滚动驱动：导航高亮 / 进度条 / 时间轴 / 巨字漂移 / 逐字点亮
   4. 入场动画：首屏编排 + 区块进入视口
   5. 文字特效：标题解码、打字机
   6. 服务卡：悬停浮现预览（跟随鼠标的 3D 倾斜）+ 作品大图弹窗
   7. 项目卡聚光 / 首屏标题景深
   8. 联系区：十六进制矩阵 + 点击解码复制 + 打印
   9. 杂项：时钟、移动端菜单、启动
   零依赖，原生 JavaScript。水波背景见 water.js。
   ============================================================ */
(() => {
  'use strict';

  /* ---------- 1. 工具与环境探测 ---------- */
  const root = document.documentElement;
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));
  const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
  // 与帧率无关的平滑逼近：rate 越大跟得越紧
  const damp = (from, to, rate, dt) => from + (to - from) * (1 - Math.exp(-rate * dt));

  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canHover = matchMedia('(hover: hover) and (pointer: fine)').matches;
  const splash = (x, y, strength, radius) => window.WaterFX && window.WaterFX.drop(x, y, strength, radius);

  // 全局指针位置（视口像素 + 归一化到 -1~1）
  const pointer = { x: innerWidth / 2, y: innerHeight / 2, nx: 0, ny: 0 };
  addEventListener('pointermove', (e) => {
    pointer.x = e.clientX;
    pointer.y = e.clientY;
    pointer.nx = (e.clientX / innerWidth) * 2 - 1;
    pointer.ny = (e.clientY / innerHeight) * 2 - 1;
  }, { passive: true });

  // 统一的逐帧循环：各模块把更新函数注册进来，共用一个 requestAnimationFrame
  const tickers = [];
  let lastFrame = performance.now();
  function loop(now) {
    const dt = Math.min(0.05, (now - lastFrame) / 1000);
    lastFrame = now;
    for (const fn of tickers) fn(dt);
    requestAnimationFrame(loop);
  }

  /* ---------- 2. 自定义光标 ----------
     只在鼠标等精确指针设备上启用；悬停在链接、按钮或带 data-cursor 的元素上时，
     外圈放大并显示 data-cursor 里的文字 */
  const cursor = $('#cursor');
  const cursorEnabled = !!(cursor && canHover && !reduceMotion);
  if (cursorEnabled) {
    root.classList.add('has-cursor');
    const ringPos = $('.cursor-ring-pos', cursor);
    const dotPos = $('.cursor-dot-pos', cursor);
    const label = $('.cursor-label', cursor);
    let rx = pointer.x;
    let ry = pointer.y;
    let seen = false;

    addEventListener('pointermove', (e) => {
      if (e.pointerType === 'touch') return;
      if (!seen) { seen = true; rx = e.clientX; ry = e.clientY; }
      cursor.classList.add('is-visible');
    }, { passive: true });
    root.addEventListener('mouseleave', () => cursor.classList.remove('is-visible'));
    addEventListener('pointerdown', () => cursor.classList.add('is-down'));
    addEventListener('pointerup', () => cursor.classList.remove('is-down'));

    const HOVER = 'a, button, [data-cursor]';
    document.addEventListener('pointerover', (e) => {
      const t = e.target.closest(HOVER);
      if (!t) return;
      const text = t.getAttribute('data-cursor') || '';
      label.textContent = text;
      cursor.classList.add('is-hover');
      cursor.classList.toggle('has-label', !!text);
    });
    document.addEventListener('pointerout', (e) => {
      const t = e.target.closest(HOVER);
      if (!t || (e.relatedTarget && t.contains(e.relatedTarget))) return;
      cursor.classList.remove('is-hover', 'has-label');
    });

    tickers.push((dt) => {
      rx = damp(rx, pointer.x, 20, dt);
      ry = damp(ry, pointer.y, 20, dt);
      dotPos.style.transform = `translate3d(${pointer.x}px, ${pointer.y}px, 0)`;
      ringPos.style.transform = `translate3d(${rx.toFixed(1)}px, ${ry.toFixed(1)}px, 0)`;
    });
  }

  /* ---------- 3. 滚动驱动 ---------- */
  const sections = $$('main > section');
  const railLinks = $$('.rail-nav a');
  const railBar = $('#railBar');
  const topBar = $('#topBar');
  const topbarSec = $('#topbarSec');
  const timeline = $('#timeline');
  const tlFill = $('#tlFill');
  const tlItems = $$('.tl-item');
  const ghost = $('#ghost');
  const statement = $('#statement');

  const layout = { vh: innerHeight, docH: 0, secTops: [], tlTop: 0, trackTop: 0, trackH: 1, nodeYs: [] };

  // 读取布局信息（尺寸变化时重新测量）；用 offsetTop 而不是 getBoundingClientRect，
  // 这样不会被入场动画里的 translate 干扰
  function measure() {
    layout.vh = innerHeight;
    layout.docH = root.scrollHeight;
    layout.secTops = sections.map((s) => s.offsetTop);

    if (timeline) {
      const sy = scrollY;
      layout.tlTop = timeline.getBoundingClientRect().top + sy;
      const track = $('.tl-track', timeline);
      layout.trackTop = track.offsetTop;
      layout.trackH = Math.max(1, track.offsetHeight);
      layout.nodeYs = tlItems.map((li) => {
        const node = $('.tl-node', li);
        return li.offsetTop + node.offsetTop + node.offsetHeight / 2;
      });
    }

    // 版式参考线：放在标题列与内容列正中间
    const body = $('.sec .sec-body');
    if (body && getComputedStyle(body.parentElement).display === 'grid') {
      const gap = parseFloat(getComputedStyle(body.parentElement).columnGap) || 0;
      root.style.setProperty('--guide-x', `${(body.getBoundingClientRect().left - gap / 2).toFixed(1)}px`);
    }

    glyphs.forEach((g) => { g.h = g.el.getBoundingClientRect().height || layout.vh * 0.5; });
  }

  let activeIndex = -1;
  function updateNav() {
    const sy = scrollY;
    const probe = sy + layout.vh * 0.4;
    let idx = 0;
    layout.secTops.forEach((top, i) => { if (top <= probe) idx = i; });
    if (idx !== activeIndex) {
      activeIndex = idx;
      railLinks.forEach((a, i) => {
        a.classList.toggle('is-active', i === idx);
        if (i === idx) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
      });
      if (topbarSec) topbarSec.textContent = `${sections[idx].dataset.sec} · ${sections[idx].dataset.label}`;
    }
    const progress = clamp(sy / Math.max(1, layout.docH - layout.vh), 0, 1);
    if (railBar) railBar.style.transform = `scaleY(${progress.toFixed(4)})`;
    if (topBar) topBar.style.transform = `scaleX(${progress.toFixed(4)})`;
  }

  // 时间轴：视口 62% 高度处为「当前时刻」，亮线推进到这里，经过的节点点亮
  function updateTimeline() {
    if (!timeline) return;
    const reach = scrollY + layout.vh * 0.62 - layout.tlTop;
    const p = clamp((reach - layout.trackTop) / layout.trackH, 0, 1);
    tlFill.style.setProperty('--p', p.toFixed(4));
    const fillEnd = layout.trackTop + p * layout.trackH;
    tlItems.forEach((li, i) => li.classList.toggle('is-lit', layout.nodeYs[i] <= fillEnd + 1));
  }

  // 背景巨字 WZQ：随滚动以不同速度向上漂移、循环出现，并随鼠标轻微横移
  const glyphs = ghost ? $$('.gl', ghost).map((el, i) => ({
    el,
    h: 0,
    x: 0,
    base: [0.14, 0.46, 0.22][i],
    speed: [0.12, 0.2, 0.16][i],
    depth: [14, 26, 20][i],
  })) : [];
  let ghostOpacity = -1;
  function updateGhost(dt) {
    if (!glyphs.length) return;
    const sy = scrollY;
    const vh = layout.vh;
    // 首屏只显示标题，离开首屏后巨字才浮现
    const op = clamp((sy - vh * 0.35) / (vh * 0.5), 0, 1);
    if (Math.abs(op - ghostOpacity) > 0.005) {
      ghostOpacity = op;
      ghost.style.opacity = op.toFixed(3);
      if (op > 0.2) ghost.classList.add('is-on');
    }
    if (op === 0) return;
    for (const g of glyphs) {
      // 「减少动态效果」模式下巨字固定不动，不跟随滚动漂移
      let y = g.base * vh;
      if (!reduceMotion) {
        const period = vh + g.h + 120;
        y = (((y - sy * g.speed + g.h) % period) + period) % period - g.h;
      }
      g.x = damp(g.x, reduceMotion ? 0 : -pointer.nx * g.depth, 2.5, dt);
      g.el.style.transform = `translate3d(${g.x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
    }
  }

  // 关于：把陈述拆成单字，滚动经过时逐字点亮
  let chars = [];
  let litCount = -1;
  if (statement && !reduceMotion) {
    // 给读屏软件保留一份完整文本，拆字后的版本对读屏隐藏
    const copy = document.createElement('div');
    copy.className = 'sr-only';
    copy.innerHTML = statement.innerHTML;
    statement.after(copy);
    statement.setAttribute('aria-hidden', 'true');

    const walker = document.createTreeWalker(statement, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      if (!node.nodeValue.trim()) return;
      const frag = document.createDocumentFragment();
      for (const ch of node.nodeValue) {
        const span = document.createElement('span');
        span.className = 'ch';
        span.textContent = ch;
        frag.appendChild(span);
      }
      node.parentNode.replaceChild(frag, node);
    });
    chars = $$('.ch', statement);
  }
  function updateStatement() {
    if (!chars.length) return;
    const r = statement.getBoundingClientRect();
    const p = clamp((layout.vh * 0.85 - r.top) / (r.height + layout.vh * 0.25), 0, 1);
    const n = Math.round(p * chars.length * 1.06);
    if (n === litCount) return;
    litCount = n;
    chars.forEach((c, i) => {
      const on = i < n;
      if (c.lit !== on) { c.lit = on; c.classList.toggle('on', on); }
    });
  }

  let scrollDirty = true;
  addEventListener('scroll', () => { scrollDirty = true; }, { passive: true });
  addEventListener('resize', () => { measure(); scrollDirty = true; });
  addEventListener('load', () => { measure(); scrollDirty = true; });
  if ('ResizeObserver' in window) {
    new ResizeObserver(() => { measure(); scrollDirty = true; }).observe(document.body);
  }

  tickers.push((dt) => {
    updateGhost(dt);
    if (!scrollDirty) return;
    scrollDirty = false;
    updateNav();
    updateTimeline();
    updateStatement();
  });

  /* ---------- 4. 入场动画 ---------- */
  const revealEls = $$('[data-reveal]');

  function onRevealed(el) {
    const desc = $('[data-typewriter]', el);
    // 项目卡描述段首已有光标竖线，打完字后末尾的光标 1.6 秒后收起，避免一张卡里两个光标
    const caretLife = desc && desc.closest('.proj') ? 1600 : 0;
    if (desc) setTimeout(() => typewrite(desc, 26, desc.textContent, caretLife), 380);
    // 入场过渡结束后移除 data-reveal，让元素恢复自己的悬停过渡
    setTimeout(() => el.removeAttribute('data-reveal'), 1500 + (parseFloat(el.style.getPropertyValue('--d')) || 0));
  }

  if (reduceMotion || !('IntersectionObserver' in window)) {
    revealEls.forEach((el) => el.classList.add('is-in'));
  } else {
    const io = new IntersectionObserver((entries) => {
      // 同一批进入视口的元素，按从上到下、从左到右的顺序错开 90ms
      let k = 0;
      entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => (a.boundingClientRect.top - b.boundingClientRect.top) || (a.boundingClientRect.left - b.boundingClientRect.left))
        .forEach((e) => {
          const el = e.target;
          el.style.setProperty('--d', String(k++ * 90));
          el.classList.add('is-in');
          io.unobserve(el);
          onRevealed(el);
        });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    revealEls.forEach((el) => io.observe(el));

    // 兜底：极少数环境里 IntersectionObserver 不回调，4 秒后全部显示，宁可没动画也不能空白
    setTimeout(() => {
      if (!$('[data-reveal].is-in')) revealEls.forEach((el) => el.classList.add('is-in'));
    }, 4000);
  }

  function intro() {
    const hero = $('.hero');
    // 双 rAF：确保初始隐藏状态先绘制出来，过渡才会触发
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (hero) hero.classList.add('is-in');
      root.classList.add('is-loaded');
    }));
    if (reduceMotion) return;

    // 标题升起落定时，在水面上砸出一圈大涟漪
    setTimeout(() => {
      const r = $('#heroTitle').getBoundingClientRect();
      splash((r.left + r.width / 2) / innerWidth, (r.top + r.height * 0.45) / innerHeight, -2.4, 0.1);
    }, 1150);

    const quote = $('#heroQuote');
    if (quote) {
      // 先固定宽度再打字，避免居中文字随字数左右晃动
      quote.style.display = 'inline-block';
      quote.style.minWidth = `${quote.getBoundingClientRect().width}px`;
      quote.style.textAlign = 'left';
      quote.textContent = '';
      setTimeout(() => typewrite(quote, 70, '先定一个能跑起来的目标，再倒推需要补什么', 2600), 1500);
    }
  }

  /* ---------- 5. 文字特效 ---------- */
  const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#/<>_+*';
  const randGlyph = () => GLYPHS[(Math.random() * GLYPHS.length) | 0];

  // 标题解码：每个字符先乱跳，再在各自的时间点定格为真实字符
  function scramble(el, duration = 1000) {
    if (reduceMotion) return;
    const final = el.dataset.final || (el.dataset.final = el.textContent);
    const token = (el.scrambleToken = (el.scrambleToken || 0) + 1);
    const settleAt = [...final].map((_, i) => 0.12 + (i / final.length) * 0.58 + Math.random() * 0.28);
    const t0 = performance.now();
    (function step(now) {
      if (el.scrambleToken !== token) return;
      const t = (now - t0) / duration;
      let out = '';
      for (let i = 0; i < final.length; i++) {
        out += final[i] === ' ' || t >= settleAt[i] ? final[i] : randGlyph();
      }
      el.textContent = out;
      if (t < 1) requestAnimationFrame(step);
      else el.textContent = final;
    })(t0);
  }

  const titles = $$('[data-scramble]');
  titles.forEach((t) => { t.dataset.final = t.textContent; t.setAttribute('aria-label', t.textContent); });
  if (!reduceMotion && 'IntersectionObserver' in window) {
    const tio = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        scramble(e.target);
        tio.unobserve(e.target);
      });
    }, { threshold: 0.8 });
    titles.forEach((t) => {
      tio.observe(t);
      t.addEventListener('pointerenter', () => scramble(t, 650));
    });
  }

  // 打字机：逐字显示，末尾留一个闪烁光标
  const typers = [];
  function typewrite(el, speed = 26, text = el.textContent, caretLife = 0) {
    if (el.dataset.typed) return;
    el.dataset.typed = '1';
    if (reduceMotion) { el.textContent = text; return; }
    el.style.minHeight = `${el.offsetHeight}px`;
    const node = document.createTextNode('');
    const caret = document.createElement('span');
    caret.className = 'caret';
    caret.setAttribute('aria-hidden', 'true');
    el.textContent = '';
    el.append(node, caret);
    const job = { el, node, text, caret, i: 0 };
    typers.push(job);
    job.timer = setInterval(() => {
      job.i++;
      node.nodeValue = text.slice(0, job.i);
      if (job.i >= text.length) finishTyping(job, caretLife);
    }, speed);
  }
  function finishTyping(job, caretLife = 0) {
    clearInterval(job.timer);
    job.node.nodeValue = job.text;
    job.el.style.minHeight = '';
    if (caretLife) setTimeout(() => job.caret.remove(), caretLife);
  }

  /* ---------- 6. 服务卡：悬停浮现预览 + 作品大图弹窗 ----------
     鼠标进入卡片 → 预览窗从鼠标附近放大浮出；
     鼠标移动 → 预览窗平滑跟随，并按鼠标位置做 3D 倾斜、按移动速度做 Z 轴摆动；
     鼠标离开 → 缩小淡出。触屏设备改为轻触切换。
     带 data-lightbox 的卡片：点击卡片（或按 Enter）打开作品大图。 */
  function openLightbox(id, e) {
    const dialog = document.getElementById(id);
    if (!dialog || dialog.open) return;
    // 弹窗在浏览器顶层，自定义光标会被它盖住：打开期间换回系统光标，并锁住背景滚动
    root.classList.remove('has-cursor');
    root.classList.add('lb-open');
    dialog.showModal();
    if (e && e.clientX) splash(e.clientX / innerWidth, e.clientY / innerHeight, -1.2, 0.05);
  }

  $$('.lightbox').forEach((dialog) => {
    dialog.addEventListener('close', () => {
      root.classList.remove('lb-open');
      if (cursorEnabled) root.classList.add('has-cursor');
    });
    // 只有点在弹窗外的遮罩上才关闭（键盘触发的 click 坐标为 0，靠 target 判断排除）
    dialog.addEventListener('click', (e) => {
      if (e.target !== dialog) return;
      const r = dialog.getBoundingClientRect();
      const inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
      if (!inside) dialog.close();
    });
    $$('[data-lightbox-close]', dialog).forEach((btn) => btn.addEventListener('click', () => dialog.close()));
  });

  $$('[data-lightbox-open]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();    // 链接本身指向大图，JS 可用时改为打开弹窗
      e.stopPropagation();   // 不再触发卡片自身的点击逻辑
      openLightbox(btn.dataset.lightboxOpen, e);
    });
  });

  $$('.work').forEach((card) => {
    const preview = $('.work-preview', card);
    if (!preview) return;

    // 预览里是视频的卡片：浮现时播放、收起时暂停，不在后台白白解码。
    // 监听 class 变化，悬停、键盘聚焦、触屏轻触三种方式都能统一处理
    const video = $('video', preview);
    if (video && !reduceMotion) {
      new MutationObserver(() => {
        if (card.classList.contains('is-hover')) video.play().catch(() => {});
        else video.pause();
      }).observe(card, { attributes: true, attributeFilter: ['class'] });
    }

    if (card.dataset.lightbox) {
      // 第一次悬停 / 聚焦 / 触摸卡片时就预加载弹窗大图，点开时不用再等
      const warmUp = () => {
        const full = $('.lb-img', document.getElementById(card.dataset.lightbox));
        if (full && !full.dataset.warmed) { full.dataset.warmed = '1'; full.loading = 'eager'; }
      };
      ['pointerenter', 'focus', 'touchstart'].forEach((type) => card.addEventListener(type, warmUp, { once: true, passive: true }));

      card.addEventListener('keydown', (e) => {
        if ((e.key === 'Enter' || e.key === ' ') && e.target === card) {
          e.preventDefault();
          openLightbox(card.dataset.lightbox);
        }
      });
    }

    if (!canHover) {
      const tip = document.createElement('span');
      tip.className = 'work-tap';
      tip.setAttribute('aria-hidden', 'true');
      tip.textContent = 'TAP TO VIEW · 轻触查看';
      card.appendChild(tip);
      card.addEventListener('click', (e) => {
        if (e.target.closest('a, button')) return;
        card.classList.toggle('is-hover');
      });
      return;
    }

    if (card.dataset.lightbox) {
      card.addEventListener('click', (e) => {
        if (e.target.closest('a, button')) return;
        openLightbox(card.dataset.lightbox, e);
      });
    }

    const s = { on: false, idle: true, x: 0, y: 0, tx: 0, ty: 0, nx: 0, ny: 0, scale: 0.7, rx: 0, ry: 0, rz: 0, ax: 0, ay: 0 };

    const aim = (clientX, clientY) => {
      const r = card.getBoundingClientRect();
      s.nx = clamp((clientX - r.left) / r.width - 0.5, -0.5, 0.5);
      s.ny = clamp((clientY - r.top) / r.height - 0.5, -0.5, 0.5);
      // 横向跟随鼠标，但预览窗不能被推出视口左右边缘
      const half = preview.offsetWidth / 2 + 12;
      const center = r.left + r.width / 2;
      s.tx = clamp(s.nx * r.width * 0.5, half - center, innerWidth - half - center);
      // 预览锚点在卡片 60% 高度处，纵向跟随鼠标但不遮住顶部标题
      s.ty = clamp(clientY - r.top - r.height * 0.6, -r.height * 0.26, r.height * 0.2);
    };
    const show = () => { s.on = true; s.idle = false; card.classList.add('is-hover'); };
    const hide = () => { s.on = false; card.classList.remove('is-hover'); s.tx = s.ty = s.nx = s.ny = 0; };

    card.addEventListener('pointerenter', (e) => {
      aim(e.clientX, e.clientY);
      s.x = s.tx * 0.6;
      s.y = s.ty * 0.6;
      show();
      splash(e.clientX / innerWidth, e.clientY / innerHeight, -0.7, 0.035);
    });
    card.addEventListener('pointermove', (e) => aim(e.clientX, e.clientY));
    card.addEventListener('pointerleave', hide);
    // 键盘聚焦时同样浮现（居中显示）
    card.addEventListener('focus', () => { if (!s.on) { s.tx = s.ty = s.nx = s.ny = 0; show(); } });
    card.addEventListener('blur', hide);

    tickers.push((dt) => {
      if (s.idle) return;
      const prevX = s.x;
      s.x = damp(s.x, s.tx, 8, dt);
      s.y = damp(s.y, s.ty, 8, dt);
      s.scale = damp(s.scale, s.on ? 1 : 0.7, 7, dt);
      const vx = (s.x - prevX) / Math.max(dt, 0.001);
      s.rz = damp(s.rz, clamp(vx * 0.014, -9, 9), 6, dt);
      s.ry = damp(s.ry, s.nx * 30, 6, dt);
      s.rx = damp(s.rx, -s.ny * 20, 6, dt);
      s.ax = damp(s.ax, s.nx, 4, dt);
      s.ay = damp(s.ay, s.ny, 4, dt);

      preview.style.transform =
        `translate(-50%, -50%) translate3d(${s.x.toFixed(1)}px, ${s.y.toFixed(1)}px, 0) ` +
        `perspective(900px) rotateX(${s.rx.toFixed(2)}deg) rotateY(${s.ry.toFixed(2)}deg) ` +
        `rotateZ(${s.rz.toFixed(2)}deg) scale(${s.scale.toFixed(3)})`;
      card.style.setProperty('--ax', s.ax.toFixed(3));
      card.style.setProperty('--ay', s.ay.toFixed(3));

      // 完全收回后停止写入，省电
      if (!s.on && s.scale < 0.705 && Math.abs(s.x) < 0.5 && Math.abs(s.y) < 0.5 && Math.abs(s.rz) < 0.05) s.idle = true;
    });
  });

  /* ---------- 7. 项目卡聚光 / 首屏标题景深 ---------- */
  $$('.proj').forEach((el) => {
    el.addEventListener('pointermove', (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty('--mx', `${(e.clientX - r.left).toFixed(0)}px`);
      el.style.setProperty('--my', `${(e.clientY - r.top).toFixed(0)}px`);
    });
  });

  // 首屏标题两层反向微移，形成景深
  const tSolid = $('.t-solid');
  const tOutline = $('.t-outline');
  if (tSolid && tOutline && canHover && !reduceMotion) {
    let hx = 0;
    let hy = 0;
    tickers.push((dt) => {
      if (scrollY > layout.vh) return;
      hx = damp(hx, pointer.nx, 3, dt);
      hy = damp(hy, pointer.ny, 3, dt);
      tSolid.style.transform = `translate3d(${(hx * 10).toFixed(2)}px, ${(hy * 6).toFixed(2)}px, 0)`;
      tOutline.style.transform = `translate3d(${(hx * -18).toFixed(2)}px, ${(hy * -11).toFixed(2)}px, 0)`;
    });
  }

  /* ---------- 8. 联系区 ---------- */
  // 8.1 十六进制矩阵：进入视口后不停刷新，光标游走；解码时把真实内容的 UTF-8 字节写进去
  const hexGrid = $('#hexGrid');
  const hex = (() => {
    if (!hexGrid) return { inject() {} };
    const HEX = '0123456789ABCDEF';
    const ROWS = 7;
    const rand4 = () => { let v = ''; for (let i = 0; i < 4; i++) v += HEX[(Math.random() * 16) | 0]; return v; };
    let cols = 12;
    let cells = [];
    let cursorAt = 0;
    const lit = new Set();

    function fit() {
      const probe = document.createElement('span');
      probe.textContent = '0000 0000 0000 0000 ';
      hexGrid.appendChild(probe);
      const cellW = probe.getBoundingClientRect().width / 4;
      probe.remove();
      cols = Math.max(4, Math.floor((hexGrid.clientWidth + cellW * 0.2) / cellW));
      const total = cols * ROWS;
      while (cells.length < total) cells.push(rand4());
      cells.length = total;
      cursorAt %= total;
      draw();
    }
    function draw() {
      const rows = [];
      for (let r = 0; r < ROWS; r++) {
        const row = [];
        for (let c = 0; c < cols; c++) {
          const i = r * cols + c;
          if (i === cursorAt) row.push(`<span class="cur">${cells[i]}</span>`);
          else if (lit.has(i)) row.push(`<span class="hl">${cells[i]}</span>`);
          else row.push(cells[i]);
        }
        rows.push(row.join(' '));
      }
      hexGrid.innerHTML = rows.join('\n');
    }
    function tick() {
      for (let k = 0; k < 7; k++) {
        const i = (Math.random() * cells.length) | 0;
        if (!lit.has(i)) cells[i] = rand4();
      }
      cursorAt = (cursorAt + 1 + ((Math.random() * 3) | 0)) % cells.length;
      draw();
    }

    fit();
    addEventListener('resize', fit);
    let timer = 0;
    if (!reduceMotion && 'IntersectionObserver' in window) {
      new IntersectionObserver(([e]) => {
        clearInterval(timer);
        if (e.isIntersecting) timer = setInterval(tick, 110);
      }).observe(hexGrid);
    }

    return {
      inject(text) {
        const bytes = new TextEncoder().encode(text);
        const start = cursorAt;
        const used = [];
        for (let b = 0, k = 0; b < bytes.length; b += 2, k++) {
          const i = (start + k) % cells.length;
          const hi = bytes[b].toString(16).padStart(2, '0');
          const lo = b + 1 < bytes.length ? bytes[b + 1].toString(16).padStart(2, '0') : '00';
          cells[i] = (hi + lo).toUpperCase();
          lit.add(i);
          used.push(i);
        }
        cursorAt = (start + used.length) % cells.length;
        draw();
        setTimeout(() => { used.forEach((i) => lit.delete(i)); }, 2800);
      },
    };
  })();

  // 8.2 点击一行：乱码解码出真实内容 → 复制到剪贴板 → 写入矩阵 → 水面溅起涟漪
  function decode(el, text, duration = 750) {
    if (reduceMotion) { el.textContent = text; return; }
    const t0 = performance.now();
    (function step(now) {
      const t = Math.min(1, (now - t0) / duration);
      const fixed = Math.floor(t * text.length);
      let out = text.slice(0, fixed);
      for (let i = fixed; i < text.length; i++) out += '.@/'.includes(text[i]) ? text[i] : randGlyph();
      el.textContent = out;
      if (t < 1) requestAnimationFrame(step);
    })(t0);
  }

  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) { /* 权限被拒时走下面的兼容方案 */ }
    const active = document.activeElement;
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;left:0;top:0;opacity:0;pointer-events:none';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      ta.remove();
      return ok;
    } catch (_) {
      return false;
    } finally {
      if (active && active.focus) active.focus({ preventScroll: true });
    }
  }

  const toast = $('#toast');
  let toastTimer = 0;
  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-on'), 2600);
  }

  $$('.crow').forEach((btn) => {
    if (btn.hasAttribute('data-print')) {
      btn.addEventListener('click', () => window.print());
      return;
    }
    const value = $('.crow-val', btn);
    const stateEl = $('.crow-state', btn);
    const real = btn.dataset.copy;
    if (!value || !real) return;

    // JS 可用时先遮住，点击后解码；读屏软件直接读到完整内容
    if (value.dataset.mask) value.textContent = value.dataset.mask;
    const key = $('.crow-key', btn).textContent.replace('//', '').trim();
    btn.setAttribute('aria-label', `复制 ${key}：${real}`);

    let resetTimer = 0;
    btn.addEventListener('click', async (e) => {
      decode(value, real);
      hex.inject(real);
      const r = btn.getBoundingClientRect();
      const cx = e.clientX || r.left + r.width / 2;
      const cy = e.clientY || r.top + r.height / 2;
      splash(cx / innerWidth, cy / innerHeight, -1.6, 0.06);

      const ok = await copyText(real);
      btn.classList.add('is-done');
      stateEl.textContent = ok ? 'COPIED ✓' : 'SELECT';
      showToast(ok ? `已复制到剪贴板：${real}` : `浏览器不允许自动复制，请手动选择：${real}`);
      clearTimeout(resetTimer);
      resetTimer = setTimeout(() => { stateEl.textContent = 'COPY'; btn.classList.remove('is-done'); }, 2800);
    });
  });

  // 打印 / 另存 PDF 前：显示真实联系方式，补完正在打字的文本
  addEventListener('beforeprint', () => {
    $$('.crow[data-copy]').forEach((btn) => { $('.crow-val', btn).textContent = btn.dataset.copy; });
    typers.forEach((job) => finishTyping(job));
  });

  /* ---------- 9. 杂项 ---------- */
  // 右下角状态卡的北京时间
  const clock = $('#clock');
  if (clock && window.Intl) {
    try {
      const fmt = new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Shanghai' });
      const tickClock = () => { clock.textContent = `${fmt.format(new Date())} UTC+8`; };
      tickClock();
      setInterval(tickClock, 15000);
    } catch (_) { /* 保留默认文字 */ }
  }

  // 移动端菜单
  const menuBtn = $('#menuBtn');
  const menu = $('#menu');
  if (menuBtn && menu) {
    const setMenu = (open) => {
      menu.hidden = !open;
      menuBtn.setAttribute('aria-expanded', String(open));
      menuBtn.setAttribute('aria-label', open ? '关闭导航菜单' : '打开导航菜单');
      document.body.style.overflow = open ? 'hidden' : '';
    };
    menuBtn.addEventListener('click', () => setMenu(menu.hidden));
    menu.addEventListener('click', (e) => { if (e.target.closest('a')) setMenu(false); });
    addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !menu.hidden) { setMenu(false); menuBtn.focus(); }
    });
    matchMedia('(min-width: 901px)').addEventListener('change', (e) => { if (e.matches) setMenu(false); });
  }

  // 启动
  measure();
  updateNav();
  updateTimeline();
  requestAnimationFrame(loop);
  intro();
})();
