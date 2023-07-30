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

  // Enable toasts
  const toasts = document.querySelectorAll(".toast");
  for (const toast of toasts) {
    new bootstrap.Toast(toast);
  }

  // Show and hide Bootstrap modal when using HTMX
  // https://blog.benoitblanchon.fr/django-htmx-modal-form/
  const modal = new bootstrap.Modal(document.getElementById("modal"));
  htmx.on("htmx:afterSwap", (e) => {
    // Response targeting #dialog => show the modal
    if (e.detail.target.id == "dialog") {
      modal.show();
    }
  });
  htmx.on("htmx:beforeSwap", (e) => {
    // Empty response targeting #dialog => hide the modal
    if (e.detail.target.id == "dialog" && !e.detail.xhr.response) {
      modal.hide();
      e.detail.shouldSwap = false;
    }
  });
});

// A site wide config that is added to the context by radis.core.site.base_context_processor
// and that can be accessed by Javascript
function getRadisConfig() {
  return JSON.parse(document.getElementById("radis_config").textContent);
}

// Alpine JS data model connected in _messages_panel.html
// A simple usage example can be found in sandbox.html and sandbox.js
function messages() {
  function capitalize(s) {
    if (typeof s !== "string") return "";
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  return {
    options: {
      nextMessageId: 1,
      duration: 30000,
    },
    messages: [],
    init: function ($el, $watch, $nextTick) {
      this.$el = $el;

      // Auto hide server messages
      const serverMessages = this.$el.getElementsByClassName("server-message");
      for (let i = 0; i < serverMessages.length; i++) {
        setTimeout(function () {
          serverMessages[i].remove();
        }, this.options.duration);
      }
    },
    addMessage: function (message) {
      message.id = this.options.nextMessageId++;
      message.title = capitalize(message.title);
      this.messages.push(message);
      const self = this;
      setTimeout(function () {
        self.messages.splice(self.messages.indexOf(message), 1);
      }, this.options.duration);
    },
    removeMessage: function (message) {
      this.messages.splice(this.messages.indexOf(message), 1);
    },
  };
}
