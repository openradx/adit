/**
 * Mermaid diagram zoom functionality
 * Works with .mermaid containers (handles Shadow DOM)
 */

function initializeZoomForContainer(container) {
  console.log("🎯 initializeZoomForContainer called");
  
  if (container.classList.contains("mermaid-zoom-initialized")) {
    console.log("⏭️ Already initialized");
    return;
  }
  
  container.classList.add("mermaid-zoom-initialized");
  console.log("✅ Creating zoom wrapper...");
  
  const wrapper = document.createElement("div");
  wrapper.className = "mermaid-zoom-wrapper";
  container.parentNode.insertBefore(wrapper, container);
  wrapper.appendChild(container);

  let scale = 1, panning = false, pointX = 0, pointY = 0, start = { x: 0, y: 0 };

  const controls = document.createElement("div");
  controls.className = "mermaid-zoom-controls";
  controls.innerHTML = '<button class="zoom-in" title="Zoom In">+</button><button class="zoom-out" title="Zoom Out">−</button><button class="zoom-reset" title="Reset">⊙</button>';
  wrapper.appendChild(controls);
  console.log("✅ Zoom controls appended!");

  const setTransform = () => container.style.transform = `translate(${pointX}px, ${pointY}px) scale(${scale})`;
  const zoomIn = () => { scale = Math.min(scale * 1.2, 5); setTransform(); };
  const zoomOut = () => { scale = Math.max(scale / 1.2, 0.5); setTransform(); };
  const resetZoom = () => { scale = 1; pointX = 0; pointY = 0; setTransform(); };

  controls.querySelector(".zoom-in").addEventListener("click", zoomIn);
  controls.querySelector(".zoom-out").addEventListener("click", zoomOut);
  controls.querySelector(".zoom-reset").addEventListener("click", resetZoom);

  wrapper.addEventListener("wheel", e => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      scale = Math.min(Math.max(scale * (e.deltaY > 0 ? 0.9 : 1.1), 0.5), 5);
      setTransform();
    }
  });

  container.addEventListener("mousedown", e => {
    e.preventDefault();
    start = { x: e.clientX - pointX, y: e.clientY - pointY };
    panning = true;
  });

  container.addEventListener("mousemove", e => {
    if (!panning) return;
    e.preventDefault();
    pointX = e.clientX - start.x;
    pointY = e.clientY - start.y;
    setTransform();
  });

  container.addEventListener("mouseup", () => panning = false);
  container.addEventListener("mouseleave", () => panning = false);
}

function setupMermaidZoom() {
  console.log("🔍 setupMermaidZoom called");
  
  const mermaidContainers = document.querySelectorAll('.mermaid');
  console.log(`Found ${mermaidContainers.length} .mermaid containers`);
  
  if (mermaidContainers.length === 0) {
    console.log("⚠️ No .mermaid containers found");
    return;
  }

  mermaidContainers.forEach((container, i) => {
    console.log(`Container ${i+1}:`, {
      tag: container.tagName,
      class: container.className,
      hasChildren: container.children.length > 0,
      hasShadowRoot: !!container.shadowRoot,
      innerHTML: container.innerHTML.substring(0, 100)
    });
    
    // Initialize if it has any content (rendered or being rendered)
    initializeZoomForContainer(container);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  console.log("📄 DOM loaded");
  setupMermaidZoom();
  
  const observer = new MutationObserver(mutations => {
    const hasMermaidChanges = mutations.some(m => 
      Array.from(m.addedNodes).some(n => 
        n.nodeType === 1 && (n.classList?.contains('mermaid') || n.querySelector?.('.mermaid'))
      )
    );
    
    if (hasMermaidChanges) {
      console.log("🔄 .mermaid container added, retrying");
      setTimeout(setupMermaidZoom, 100);
    }
  });
  
  observer.observe(document.querySelector('.md-content') || document.body, { childList: true, subtree: true });
});

setTimeout(() => { console.log("⏱️ 500ms"); setupMermaidZoom(); }, 500);
setTimeout(() => { console.log("⏱️ 1500ms"); setupMermaidZoom(); }, 1500);
setTimeout(() => { console.log("⏱️ 3000ms"); setupMermaidZoom(); }, 3000);
