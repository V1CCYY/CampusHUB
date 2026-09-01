(function () {
  "use strict";

  document.querySelectorAll(".accordion-item").forEach((item) => {
    const trigger = item.querySelector(".accordion-trigger");
    if (!trigger) return;

    trigger.addEventListener("click", () => {
      const isOpen = item.classList.contains("open");

      item
        .closest(".accordion")
        .querySelectorAll(".accordion-item.open")
        .forEach((openItem) => {
          if (openItem !== item) openItem.classList.remove("open");
        });

      item.classList.toggle("open", !isOpen);
    });
  });
})();
