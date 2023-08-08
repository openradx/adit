"use strict";

function ready(fn) {
  if (document.readyState !== "loading") {
    fn();
    return;
  }
  document.addEventListener("DOMContentLoaded", fn);
}

ready(function () {
  // Enable Bootstrap tooltips
  const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  for (const tooltip of tooltips) {
    new bootstrap.Tooltip(tooltip);
  }
});

// A site wide config that is added to the context by adit.core.site.base_context_processor
// and that can be accessed by Javascript
function getConfig() {
  const configNode = document.getElementById("public");
  if (!configNode || !configNode.textContent) {
    throw new Error("Missing app config.");
  }
  return JSON.parse(configNode.textContent);
}

// Update session properties on the server (used to retain specific form fields on page reload)
function updatePreferences(route, data) {
  const formData = new FormData();
  for (const key in data) {
    formData.append(key, data[key]);
  }

  let url;
  if (route) {
    url = `/${route}/update-preferences/`;
  } else {
    url = "/update-preferences/";
  }

  const config = getConfig();
  const request = new Request(url, {
    method: "POST",
    headers: { "X-CSRFToken": config.csrf_token },
    mode: "same-origin", // Do not send CSRF token to another domain.
    body: formData,
  });

  fetch(request).then(function () {
    const config = getConfig();
    if (config.debug) {
      console.log("Saved properties to session", data);
    }
  });
}

// Add message to the messages panel
function showMessage(level, title, text) {
  window.dispatchEvent(
    new CustomEvent("core:add-message", {
      detail: {
        level: level,
        title: title,
        text: text,
      },
    })
  );
}

// Alpine data model connected in _messages_panel.html to show and
// interact with messages in the messages panel.
function messagesPanel(panelEl) {
  function capitalize(s) {
    if (typeof s !== "string") return "";
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  return {
    options: {
      duration: 30000, // 30 seconds
    },
    /** @type{Array} */
    messages: [], // List of messages created by the client
    init: function () {
      // Initialize messages created by the server
      const messageEls = panelEl.getElementsByClassName("server-message");
      for (const messageEl of messageEls) {
        this.initMessage(messageEl);
      }
    },
    // Also called for every messaged created by the client
    initMessage: function (messageEl) {
      new bootstrap.Toast(messageEl, {
        delay: this.options.duration,
      }).show();
    },
    /**
     * Add a message to the message list. Call the showMessage function above to
     * add messages to the list from another function or script.
     * @param {object} message
     * @param {("success"|"warning"|"error")} message.level
     * @param {string} message.title
     * @param {string} message.text
     */
    addMessage: function (message) {
      message.title = capitalize(message.title);
      this.messages.push(message);
    },
  };
}
