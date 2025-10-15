document.addEventListener("DOMContentLoaded", function () {
  function initializeMermaid() {
    if (typeof mermaid !== "undefined") {
      try {
        mermaid.initialize({
          startOnLoad: true,
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

  if (!initializeMermaid()) {
    setTimeout(initializeMermaid, 50);
  }
});

if (typeof app !== "undefined" && app.document$) {
  app.document$.subscribe(function () {
    setTimeout(function () {
      if (typeof mermaid !== "undefined") {
        mermaid.init();
      }
    }, 50);
  });
}
