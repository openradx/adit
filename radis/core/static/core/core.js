"use strict";

/**
 * Execute a function when the DOM is ready.
 * @param {Function} fn
 * @returns {void}
 */
function ready(fn) {
  if (document.readyState !== "loading") {
    fn();
    return;
  }
  // @ts-ignore
  document.addEventListener("DOMContentLoaded", fn);
}

/**
 * Initialize Bootstrap stuff.
 */
ready(function () {
  // Enable Bootstrap tooltips
  const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  for (const tooltip of tooltips) {
    new bootstrap.Tooltip(tooltip);
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

/**
 * Get the app config from the DOM that was added by the Django context processor:
 * radis.core.site.base_context_processor (public key)
 * @returns {object} config
 */
function getConfig() {
  const configNode = document.getElementById("public");
  if (!configNode || !configNode.textContent) {
    throw new Error("Missing app config.");
  }
  return JSON.parse(configNode.textContent);
}

/**
 * Update user preferences on the server (sends an AJAX request to the server).
 * @param {string} route
 * @param {object} data
 * @returns {void}
 */
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

/**
 * Show a new toast (put on top of the toasts stack).
 * @param {("success"|"warning"|"error")} level
 * @param {string} title
 * @param {string} text
 * @returns {void}
 */
function showToast(level, title, text) {
  window.dispatchEvent(
    new CustomEvent("core:add-toast", {
      detail: {
        level: level,
        title: title,
        text: text,
      },
    })
  );
}

/**
 * Alpine data model for the toasts panel.
 * @param {HTMLElement} panelEl
 * @returns {object} Alpine data model
 */
function toastsPanel(panelEl) {
  /**
   * Helper function to capitalize a string
   * @param {string} str
   * @returns {string}
   */
  function capitalize(str) {
    if (typeof str !== "string") return "";
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  return {
    options: {
      duration: 30000, // 30 seconds
    },
    /**
     * An array of toasts created by the client.
     * @type{Array}
     * @property {("success"|"warning"|"error")} level
     * @property {string} title
     * @property {string} text
     */
    toasts: [],
    /**
     * Called for every new toast to initialize it.
     * @param {HTMLElement} toastEl
     * @returns {void}
     */
    initToast: function (toastEl) {
      new bootstrap.Toast(toastEl, {
        delay: this.options.duration,
      }).show();
    },
    /**
     * Add a toast to the toasts list. Call the showToast function above to
     * add toasts to the list from another function or script.
     * @param {object} toast
     * @param {("success"|"warning"|"error")} toast.level
     * @param {string} toast.title
     * @param {string} toast.text
     * @returns {void}
     */
    addToast: function (toast) {
      toast.title = capitalize(toast.title);
      this.toasts.push(toast);
    },
  };
}
