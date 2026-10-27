(function () {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";
  var PALETTE = ["#22d3ee", "#3b82f6", "#a78bfa", "#f59e0b", "#34d399", "#94a3b8"];
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var dataNode = document.getElementById("dash-data");
  if (!dataNode) return;

  var data;
  try {
    data = JSON.parse(dataNode.textContent);
  } catch (e) {
    return;
  }

  /* ---------- helpers ---------- */

  function svgEl(name, attrs, text) {
    var node = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach(function (k) {
      node.setAttribute(k, attrs[k]);
    });
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function htmlEl(name, className, text) {
    var node = document.createElement(name);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function truncate(text, max) {
    text = String(text);
    return text.length > max ? text.slice(0, max - 1) + "\u2026" : text;
  }

  function sum(items) {
    return items.reduce(function (t, i) { return t + i.value; }, 0);
  }

  function showEmpty(box, message) {
    box.innerHTML = "";
    box.appendChild(htmlEl("div", "chart-empty", message));
  }

  function makeTooltip(box) {
    var tip = htmlEl("div", "chart-tip");
    box.appendChild(tip);
    return {
      show: function (evt, html) {
        var rect = box.getBoundingClientRect();
        tip.innerHTML = html;
        tip.style.left = Math.min(Math.max(evt.clientX - rect.left, 50), rect.width - 50) + "px";
        tip.style.top = evt.clientY - rect.top + "px";
        tip.classList.add("show");
      },
      hide: function () {
        tip.classList.remove("show");
      }
    };
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function legend(box, items, total) {
    var wrap = htmlEl("div", "chart-legend");
    items.forEach(function (item, idx) {
      var chip = htmlEl("span");
      var dot = htmlEl("i");
      dot.style.background = item.color || PALETTE[idx % PALETTE.length];
      chip.appendChild(dot);
      chip.appendChild(document.createTextNode(truncate(item.label, 22) + " "));
      var pct = total ? Math.round((item.value / total) * 100) : 0;
      chip.appendChild(htmlEl("b", "", item.value + (total ? " (" + pct + "%)" : "")));
      wrap.appendChild(chip);
    });
    box.appendChild(wrap);
  }

  /* ---------- rosca ---------- */

  function donut(id, items, centerText, emptyMsg) {
    var box = document.getElementById(id);
    if (!box) return;

    items = items.filter(function (i) { return i.value > 0; });
    var total = sum(items);
    if (!total) return showEmpty(box, emptyMsg);

    box.innerHTML = "";
    var size = 220, c = size / 2, r = 74, stroke = 30;
    var circ = 2 * Math.PI * r;
    var svg = svgEl("svg", { viewBox: "0 0 " + size + " " + size, role: "img", "aria-label": centerText });
    svg.style.maxWidth = "230px";
    svg.style.margin = "0 auto";

    var ring = svgEl("circle", { cx: c, cy: c, r: r, "stroke-width": stroke });
    ring.style.fill = "none";
    ring.style.stroke = "var(--border-soft)";
    svg.appendChild(ring);

    var tip = makeTooltip(box);
    var offset = 0;
    var gap = items.length > 1 ? 2 : 0;

    items.forEach(function (item, idx) {
      var len = (item.value / total) * circ;
      var seg = svgEl("circle", {
        cx: c, cy: c, r: r, fill: "none",
        stroke: item.color || PALETTE[idx % PALETTE.length],
        "stroke-width": stroke,
        "stroke-dasharray": Math.max(len - gap, 0.5) + " " + circ,
        "stroke-dashoffset": -offset,
        transform: "rotate(-90 " + c + " " + c + ")",
        "class": "c-seg"
      });
      offset += len;

      seg.addEventListener("mousemove", function (e) {
        box.classList.add("has-hover");
        seg.classList.add("is-on");
        tip.show(e, "<b>" + escapeHtml(item.label) + "</b><br>" + item.value + " (" + Math.round((item.value / total) * 100) + "%)");
      });
      seg.addEventListener("mouseleave", function () {
        box.classList.remove("has-hover");
        seg.classList.remove("is-on");
        tip.hide();
      });

      if (!reduceMotion) {
        seg.style.opacity = "0";
        setTimeout(function () {
          seg.style.transition = "opacity 0.5s ease";
          seg.style.opacity = "";
        }, 80 + idx * 110);
      }
      svg.appendChild(seg);
    });

    svg.appendChild(svgEl("text", { x: c, y: c + 6, "text-anchor": "middle", "class": "c-center-num" }, String(total)));
    svg.appendChild(svgEl("text", { x: c, y: c + 26, "text-anchor": "middle", "class": "c-center-txt" }, centerText));

    box.appendChild(svg);
    legend(box, items, total);
  }

  /* ---------- barras horizontais (HTML/CSS, texto sempre legível) ---------- */

  function hbars(id, items, unit, emptyMsg) {
    var box = document.getElementById(id);
    if (!box) return;
    if (!items.length) return showEmpty(box, emptyMsg);

    box.innerHTML = "";
    var max = Math.max.apply(null, items.map(function (i) { return i.value; }).concat([1]));
    var list = htmlEl("div", "hbar-list");

    items.forEach(function (item, idx) {
      var row = htmlEl("div", "hbar-row");
      row.title = item.label + ": " + item.value + (unit ? " " + unit : "");

      row.appendChild(htmlEl("div", "hbar-label", item.label));

      var track = htmlEl("div", "hbar-track");
      var fill = htmlEl("div", "hbar-fill");
      fill.style.background = item.color || PALETTE[0];
      fill.style.width = (item.value > 0 ? Math.max((item.value / max) * 100, 2) : 0) + "%";
      fill.style.animationDelay = idx * 70 + "ms";
      track.appendChild(fill);
      row.appendChild(track);

      row.appendChild(htmlEl("div", "hbar-value", String(item.value)));
      list.appendChild(row);
    });

    box.appendChild(list);
  }

  /* ---------- linhas (atividade) ---------- */

  function niceMax(v) {
    if (v <= 4) return 4;
    var step = Math.pow(10, Math.floor(Math.log10(v / 4)));
    var steps = [1, 2, 2.5, 5, 10];
    for (var i = 0; i < steps.length; i++) {
      if (steps[i] * step * 4 >= v) return steps[i] * step * 4;
    }
    return Math.ceil(v / 4) * 4;
  }

  function smoothPath(points) {
    var d = "M" + points[0][0] + "," + points[0][1];
    for (var i = 1; i < points.length; i++) {
      var p0 = points[i - 1], p1 = points[i];
      var mx = (p0[0] + p1[0]) / 2;
      d += " C" + mx + "," + p0[1] + " " + mx + "," + p1[1] + " " + p1[0] + "," + p1[1];
    }
    return d;
  }

  function lines(id, labels, series, emptyMsg) {
    var box = document.getElementById(id);
    if (!box) return;

    var all = [];
    series.forEach(function (s) { all = all.concat(s.values); });
    if (!all.some(function (v) { return v > 0; })) return showEmpty(box, emptyMsg);

    box.innerHTML = "";
    var W = 640, H = 270;
    var pad = { l: 32, r: 16, t: 14, b: 32 };
    var iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
    var yMax = niceMax(Math.max.apply(null, all));
    var n = labels.length;

    function px(i) { return pad.l + (n === 1 ? iw / 2 : (i / (n - 1)) * iw); }
    function py(v) { return pad.t + ih - (v / yMax) * ih; }

    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Atividade dos últimos 7 dias" });
    var defs = svgEl("defs");
    svg.appendChild(defs);

    // grade + eixo Y
    for (var t = 0; t <= 4; t++) {
      var val = (yMax / 4) * t;
      var y = py(val);
      svg.appendChild(svgEl("line", { x1: pad.l, x2: W - pad.r, y1: y, y2: y, "class": "c-grid" }));
      svg.appendChild(svgEl("text", { x: pad.l - 8, y: y + 4, "text-anchor": "end", "class": "c-axis" }, String(Math.round(val * 10) / 10)));
    }

    // eixo X
    labels.forEach(function (lb, i) {
      svg.appendChild(svgEl("text", { x: px(i), y: H - 10, "text-anchor": "middle", "class": "c-axis" }, lb));
    });

    // séries
    var dotsBySeries = [];
    series.forEach(function (s, si) {
      var gid = "dash-grad-" + si;
      var grad = svgEl("linearGradient", { id: gid, x1: 0, y1: 0, x2: 0, y2: 1 });
      grad.appendChild(svgEl("stop", { offset: "0%", "stop-color": s.color, "stop-opacity": "0.30" }));
      grad.appendChild(svgEl("stop", { offset: "100%", "stop-color": s.color, "stop-opacity": "0" }));
      defs.appendChild(grad);

      var pts = s.values.map(function (v, i) { return [px(i), py(v)]; });
      var line = smoothPath(pts);
      var area = line + " L" + px(n - 1) + "," + (pad.t + ih) + " L" + px(0) + "," + (pad.t + ih) + " Z";

      svg.appendChild(svgEl("path", { d: area, fill: "url(#" + gid + ")", "class": "c-line-area" }));
      svg.appendChild(svgEl("path", { d: line, fill: "none", stroke: s.color, "stroke-width": 2.5, "stroke-linecap": "round", "stroke-linejoin": "round" }));

      var dots = pts.map(function (p) {
        var dot = svgEl("circle", { cx: p[0], cy: p[1], r: 3.5, stroke: s.color, "stroke-width": 2, "class": "c-dot" });
        dot.style.fill = "var(--bg-app)";
        svg.appendChild(dot);
        return dot;
      });
      dotsBySeries.push(dots);
    });

    // guia vertical + hover por coluna
    var guide = svgEl("line", { y1: pad.t, y2: pad.t + ih, "class": "c-grid", "stroke-dasharray": "4 4", opacity: 0 });
    svg.appendChild(guide);

    var tip = makeTooltip(box);
    var colW = n === 1 ? iw : iw / (n - 1);

    labels.forEach(function (lb, i) {
      var hit = svgEl("rect", { x: px(i) - colW / 2, y: pad.t, width: colW, height: ih, fill: "transparent" });
      hit.addEventListener("mousemove", function (e) {
        guide.setAttribute("x1", px(i));
        guide.setAttribute("x2", px(i));
        guide.setAttribute("opacity", 1);
        dotsBySeries.forEach(function (dots, si) {
          dots.forEach(function (d, di) { d.setAttribute("r", di === i ? 5.5 : 3.5); });
        });
        var rows = series.map(function (s) {
          return '<span style="color:' + s.color + '">\u25CF</span> ' + escapeHtml(s.name) + ": <b>" + s.values[i] + "</b>";
        }).join("<br>");
        tip.show(e, "<b>" + escapeHtml(lb) + "</b><br>" + rows);
      });
      hit.addEventListener("mouseleave", function () {
        guide.setAttribute("opacity", 0);
        dotsBySeries.forEach(function (dots) { dots.forEach(function (d) { d.setAttribute("r", 3.5); }); });
        tip.hide();
      });
      svg.appendChild(hit);
    });

    box.appendChild(svg);

    var wrap = htmlEl("div", "chart-legend");
    series.forEach(function (s) {
      var chip = htmlEl("span");
      var dot = htmlEl("i");
      dot.style.background = s.color;
      chip.appendChild(dot);
      chip.appendChild(document.createTextNode(s.name + " "));
      chip.appendChild(htmlEl("b", "", "(" + sum(s.values.map(function (v) { return { value: v }; })) + " no período)"));
      wrap.appendChild(chip);
    });
    box.appendChild(wrap);
  }

  /* ---------- contagem animada dos cards ---------- */

  function countUp() {
    var nodes = document.querySelectorAll("[data-count]");
    nodes.forEach(function (node) {
      var target = parseInt(node.getAttribute("data-count"), 10);
      if (isNaN(target) || target <= 0 || reduceMotion) return;
      var duration = 700, start = null;
      node.textContent = "0";
      function step(ts) {
        if (start === null) start = ts;
        var p = Math.min((ts - start) / duration, 1);
        var eased = 1 - Math.pow(1 - p, 3);
        node.textContent = Math.round(target * eased);
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  }

  /* ---------- montagem ---------- */

  lines("chart-atividade", data.atividade.labels, data.atividade.series,
    "Sem saídas nem requisições nos últimos 7 dias.");
  donut("chart-requisicoes", data.requisicoes, "requisições", "Nenhuma requisição registrada ainda.");
  hbars("chart-menores", data.menores_estoques, "un", "Nenhuma peça cadastrada ainda.");
  donut("chart-local", data.estoque_local, "unidades", "Sem estoque para exibir.");
  donut("chart-salas", data.salas_status, "salas", "Nenhuma sala cadastrada ainda.");
  hbars("chart-computadores", data.computadores_sala, "computadores", "Nenhuma sala cadastrada ainda.");
  countUp();
})();
