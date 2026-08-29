/* ============================================================
   伍梓侨 · 个人简历  交互脚本
   ------------------------------------------------------------
   四件事：
     1. 深 / 浅主题切换，选择记忆到 localStorage
     2. 移动端汉堡菜单
     3. 滚动进入视口时的渐显（IntersectionObserver）
     4. 页面滚动后给顶栏加分隔线
   零依赖，原生 JS。
   ============================================================ */
(function () {
  'use strict';

  /* ---------- 1. 主题切换 ---------- */
  var STORAGE_KEY = 'wzq-resume-theme';
  var root = document.documentElement;
  var toggle = document.getElementById('themeToggle');

  // 读取上次的选择；没有记录就跟随系统（不写 data-theme，交给 CSS 媒体查询）
  try {
    var saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'dark' || saved === 'light') {
      root.setAttribute('data-theme', saved);
    }
  } catch (e) {
    /* 隐私模式下 localStorage 可能不可用，忽略即可，不影响页面 */
  }

  if (toggle) {
    toggle.addEventListener('click', function () {
      // 当前实际生效的主题：优先看手动设置，其次看系统偏好
      var current = root.getAttribute('data-theme');
      if (!current) {
        current = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      var next = current === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem(STORAGE_KEY, next); } catch (e) {}
    });
  }

  /* ---------- 2. 移动端汉堡菜单 ---------- */
  var navToggle = document.getElementById('navToggle');
  var navMenu = document.getElementById('navMenu');

  if (navToggle && navMenu) {
    navToggle.addEventListener('click', function () {
      var open = navMenu.classList.toggle('is-open');
      navToggle.setAttribute('aria-expanded', String(open));
      navToggle.setAttribute('aria-label', open ? '收起导航菜单' : '展开导航菜单');
    });

    // 点击任一导航项后自动收起，避免挡住内容
    navMenu.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        navMenu.classList.remove('is-open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });

    // Esc 关闭
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && navMenu.classList.contains('is-open')) {
        navMenu.classList.remove('is-open');
        navToggle.setAttribute('aria-expanded', 'false');
        navToggle.focus();
      }
    });
  }

  /* ---------- 3. 滚动渐显 ----------
     内容默认可见（见 style.css 第 12 节）。只有确认能正常做动画时，
     才加 .js-reveal 把元素藏起来——否则宁可不要动画，也不能让页面空白。 */
  var reveals = document.querySelectorAll('.reveal');
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (!reduceMotion && 'IntersectionObserver' in window && reveals.length) {
    root.classList.add('js-reveal');

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);   // 只触发一次，不做来回闪动
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });

    reveals.forEach(function (el) { io.observe(el); });

    // 兜底：某些环境（页面不合成帧、后台标签页等）下 IntersectionObserver
    // 可能一直不回调。3 秒后若首屏元素仍未显示，就全部放出来。
    setTimeout(function () {
      if (!document.querySelector('.reveal.is-visible')) {
        reveals.forEach(function (el) { el.classList.add('is-visible'); });
      }
    }, 3000);
  }

  /* ---------- 4. 顶栏滚动分隔线 ---------- */
  var header = document.getElementById('siteHeader');
  if (header) {
    var ticking = false;
    var onScroll = function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(function () {
        header.classList.toggle('is-scrolled', window.scrollY > 8);
        ticking = false;
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }
})();
