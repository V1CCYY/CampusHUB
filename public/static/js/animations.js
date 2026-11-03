(function () {
  "use strict";

  const reduceMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;
  const finePointer = window.matchMedia("(pointer: fine)").matches;

  const revealEls = document.querySelectorAll(".reveal");

  if (revealEls.length) {
    if (reduceMotion || !("IntersectionObserver" in window)) {
      revealEls.forEach((el) => el.classList.add("in-view"));
    } else {
      const revealObserver = new IntersectionObserver(
        (entries, observer) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("in-view");
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
      );

      revealEls.forEach((el) => revealObserver.observe(el));
    }
  }

  if (!reduceMotion && finePointer) {
    document.querySelectorAll(".tilt-card").forEach((card) => {
      let frame = null;

      card.addEventListener("mousemove", (e) => {
        const rect = card.getBoundingClientRect();
        const px = (e.clientX - rect.left) / rect.width - 0.5;
        const py = (e.clientY - rect.top) / rect.height - 0.5;

        if (frame) cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          card.style.transform = `perspective(800px) rotateX(${(-py * 6).toFixed(
            2
          )}deg) rotateY(${(px * 6).toFixed(2)}deg) translateY(-3px)`;
        });
      });

      card.addEventListener("mouseleave", () => {
        if (frame) cancelAnimationFrame(frame);
        card.style.transform = "";
      });
    });
  }

  if (!reduceMotion && finePointer) {
    const hero = document.querySelector(".hero-container");
    const heroContent = document.querySelector(".main-content");

    if (hero && heroContent) {
      let frame = null;

      hero.addEventListener("mousemove", (e) => {
        const rect = hero.getBoundingClientRect();
        const px = (e.clientX - rect.left) / rect.width - 0.5;
        const py = (e.clientY - rect.top) / rect.height - 0.5;

        if (frame) cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          heroContent.style.transform = `translate3d(${(px * -10).toFixed(
            2
          )}px, ${(py * -8).toFixed(2)}px, 0)`;
        });
      });

      hero.addEventListener("mouseleave", () => {
        if (frame) cancelAnimationFrame(frame);
        heroContent.style.transform = "";
      });
    }
  }
})();
