/**
 * Mermaid diagram zoom functionality
 * Works with .mermaid containers (handles Shadow DOM)
 */

// Constants
const RETRY_INTERVALS_MS = [100, 500, 1500, 3000];

function initializeZoomForContainer(container) {
  if (container.classList.contains("mermaid-zoom-initialized")) {
    return;
  }

  container.classList.add("mermaid-zoom-initialized");

  const wrapper = document.createElement("div");
  wrapper.className = "mermaid-zoom-wrapper";
  container.parentNode.insertBefore(wrapper, container);
  wrapper.appendChild(container);

  let scale = 1,
    panning = false,
    pointX = 0,
    pointY = 0,
    start = { x: 0, y: 0 };

  const controls = document.createElement("div");
  controls.className = "mermaid-zoom-controls";
  controls.innerHTML =
    '<button class="zoom-in" title="Zoom In">+</button><button class="zoom-out" title="Zoom Out">−</button><button class="zoom-reset" title="Reset">⊙</button>';
  wrapper.appendChild(controls);

  const setTransform = () =>
    (container.style.transform = `translate(${pointX}px, ${pointY}px) scale(${scale})`);
  const zoomIn = () => {
    scale = Math.min(scale * 1.2, 5);
    setTransform();
  };
  const zoomOut = () => {
    scale = Math.max(scale / 1.2, 0.5);
    setTransform();
  };
  const resetZoom = () => {
    scale = 1;
    pointX = 0;
    pointY = 0;
    setTransform();
  };

  controls.querySelector(".zoom-in").addEventListener("click", zoomIn);
  controls.querySelector(".zoom-out").addEventListener("click", zoomOut);
  controls.querySelector(".zoom-reset").addEventListener("click", resetZoom);

  wrapper.addEventListener("wheel", (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      scale = Math.min(Math.max(scale * (e.deltaY > 0 ? 0.9 : 1.1), 0.5), 5);
      setTransform();
    }
  });

  container.addEventListener("mousedown", (e) => {
    e.preventDefault();
    start = { x: e.clientX - pointX, y: e.clientY - pointY };
    panning = true;
  });

  container.addEventListener("mousemove", (e) => {
    if (!panning) return;
    e.preventDefault();
    pointX = e.clientX - start.x;
    pointY = e.clientY - start.y;
    setTransform();
  });

  container.addEventListener("mouseup", () => (panning = false));
  container.addEventListener("mouseleave", () => (panning = false));
}

function setupMermaidZoom() {
  const mermaidContainers = document.querySelectorAll(".mermaid");

  if (mermaidContainers.length === 0) {
    return;
  }

  mermaidContainers.forEach((container) => {
    initializeZoomForContainer(container);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupMermaidZoom();

  const observer = new MutationObserver((mutations) => {
    const hasMermaidChanges = mutations.some((m) =>
      Array.from(m.addedNodes).some(
        (n) =>
          n.nodeType === 1 &&
          (n.classList?.contains("mermaid") || n.querySelector?.(".mermaid")),
      ),
    );

    if (hasMermaidChanges) {
      setTimeout(setupMermaidZoom, RETRY_INTERVALS_MS[0]);
    }
  });

  observer.observe(document.querySelector(".md-content") || document.body, {
    childList: true,
    subtree: true,
  });
});

// Retry at intervals to catch late-rendering diagrams
RETRY_INTERVALS_MS.slice(1).forEach((interval) => {
  setTimeout(setupMermaidZoom, interval);
});
