// Optimized Mermaid configuration for fast loading
document.addEventListener("DOMContentLoaded", function () {
  // Quick initialization function
  function initializeMermaid() {
    if (typeof mermaid !== "undefined") {
      try {
        mermaid.initialize({
          startOnLoad: true, // Let mermaid handle auto-loading
          theme: "default",
          securityLevel: "loose",
          themeVariables: {
            primaryColor: "#3f51b5",
            primaryTextColor: "#fff",
            primaryBorderColor: "#3f51b5",
            lineColor: "#3f51b5",
            secondaryColor: "#e8eaf6",
            tertiaryColor: "#fff",
          },
          flowchart: {
            useMaxWidth: true,
            htmlLabels: true,
          },
          sequence: {
            useMaxWidth: true,
            wrap: true,
          },
        });
        return true;
      } catch (error) {
        console.error("Mermaid initialization error:", error);
        return false;
      }
    }
    return false;
  }

  // Try immediate initialization
  if (!initializeMermaid()) {
    // Quick retry if needed
    setTimeout(initializeMermaid, 50);
  }
});

// Handle Material theme navigation efficiently
if (typeof app !== "undefined" && app.document$) {
  app.document$.subscribe(function () {
    // Quick re-render for new pages
    setTimeout(function () {
      if (typeof mermaid !== "undefined") {
        mermaid.init();
      }
    }, 50);
  });
}
