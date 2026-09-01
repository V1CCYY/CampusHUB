(function () {
  "use strict";

  const reduceMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  const canvas = document.createElement("canvas");
  canvas.id = "particles-canvas";
  canvas.setAttribute("aria-hidden", "true");
  document.body.insertBefore(canvas, document.body.firstChild);
  const ctx = canvas.getContext("2d", { alpha: false });

  const glow = document.createElement("div");
  glow.className = "cursor-glow";
  document.body.insertBefore(glow, canvas.nextSibling);

  const BG = "#05070c";
  const LINE_RGB = "56, 189, 248";
  const DOT_RGB = "148, 197, 255";

  let width = 0;
  let height = 0;
  let dpr = 1;
  let particles = [];
  let running = false;
  let tabVisible = true;

  const mouse = { x: -9999, y: -9999, active: false };
  const glowPos = { x: -9999, y: -9999, tx: -9999, ty: -9999 };

  const LINK_DIST = 145;
  const MOUSE_DIST = 200;

  function particleCount() {
    const area = width * height;
    const density = Math.round(area / 17000);
    const cap = window.matchMedia("(max-width: 720px)").matches ? 60 : 150;
    return Math.max(32, Math.min(cap, density));
  }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function buildParticles() {
    const count = particleCount();
    particles = new Array(count).fill(0).map(() => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.22,
      vy: (Math.random() - 0.5) * 0.22,
      r: Math.random() * 1.5 + 0.7,
      pulse: Math.random() * Math.PI * 2,
    }));
  }

  function drawFrame() {
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, width, height);

    // brilho ambiente sutil, próximo ao topo
    const g = ctx.createRadialGradient(
      width * 0.5,
      height * 0.1,
      0,
      width * 0.5,
      height * 0.1,
      Math.max(width, height) * 0.75
    );
    g.addColorStop(0, "rgba(56, 189, 248, 0.05)");
    g.addColorStop(1, "rgba(5, 7, 12, 0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, width, height);

    const n = particles.length;

    for (let i = 0; i < n; i++) {
      const p = particles[i];

      if (!reduceMotion) {
        p.x += p.vx;
        p.y += p.vy;
        p.pulse += 0.018;

        if (p.x < -30) p.x = width + 30;
        if (p.x > width + 30) p.x = -30;
        if (p.y < -30) p.y = height + 30;
        if (p.y > height + 30) p.y = -30;

        if (mouse.active) {
          const dx = p.x - mouse.x;
          const dy = p.y - mouse.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          if (dist < MOUSE_DIST) {
            const force = ((MOUSE_DIST - dist) / MOUSE_DIST) * 1.2;
            p.x += (dx / dist) * force;
            p.y += (dy / dist) * force;
          }
        }
      }

      for (let j = i + 1; j < n; j++) {
        const q = particles[j];
        const dx = p.x - q.x;
        const dy = p.y - q.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < LINK_DIST) {
          const alpha = (1 - dist / LINK_DIST) * 0.32;
          ctx.strokeStyle = `rgba(${LINE_RGB}, ${alpha})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(q.x, q.y);
          ctx.stroke();
        }
      }

      if (mouse.active) {
        const dx = p.x - mouse.x;
        const dy = p.y - mouse.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < MOUSE_DIST) {
          const alpha = (1 - dist / MOUSE_DIST) * 0.55;
          ctx.strokeStyle = `rgba(125, 211, 252, ${alpha})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(mouse.x, mouse.y);
          ctx.stroke();
        }
      }

      const flicker = reduceMotion ? 0.6 : 0.5 + Math.sin(p.pulse) * 0.25;
      ctx.beginPath();
      ctx.fillStyle = `rgba(${DOT_RGB}, ${flicker})`;
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    }

    if (mouse.active) {
      ctx.beginPath();
      ctx.fillStyle = "rgba(125, 211, 252, 0.85)";
      ctx.arc(mouse.x, mouse.y, 2.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function tick() {
    drawFrame();

    // glow segue o mouse com suavização (lerp)
    glowPos.x += (glowPos.tx - glowPos.x) * 0.12;
    glowPos.y += (glowPos.ty - glowPos.y) * 0.12;
    glow.style.transform = `translate3d(${glowPos.x}px, ${glowPos.y}px, 0)`;

    if (tabVisible && !reduceMotion) {
      requestAnimationFrame(tick);
    } else {
      running = false;
    }
  }

  function setPointer(x, y) {
    mouse.x = x;
    mouse.y = y;
    mouse.active = true;
    glowPos.tx = x;
    glowPos.ty = y;
    glow.style.opacity = "1";
  }

  function clearPointer() {
    mouse.active = false;
    glow.style.opacity = "0";
  }

  window.addEventListener(
    "mousemove",
    (e) => setPointer(e.clientX, e.clientY),
    { passive: true }
  );
  window.addEventListener("mouseleave", clearPointer, { passive: true });
  window.addEventListener(
    "touchmove",
    (e) => {
      if (e.touches && e.touches[0]) {
        setPointer(e.touches[0].clientX, e.touches[0].clientY);
      }
    },
    { passive: true }
  );
  window.addEventListener("touchend", clearPointer, { passive: true });

  let resizeTimer = null;
  window.addEventListener(
    "resize",
    () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        resize();
        buildParticles();
        if (reduceMotion) drawFrame();
      }, 150);
    },
    { passive: true }
  );

  document.addEventListener("visibilitychange", () => {
    tabVisible = !document.hidden;
    if (tabVisible && !reduceMotion && !running) {
      running = true;
      tick();
    }
  });

  resize();
  buildParticles();
  drawFrame();

  if (!reduceMotion) {
    running = true;
    tick();
  }
})();
