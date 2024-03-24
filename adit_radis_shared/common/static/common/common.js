"use strict";

/**
 * Execute a function when the DOM is ready.
 * @param {EventListener} fn
 * @returns {void}
 */
function ready(fn) {
  if (document.readyState !== "loading") {
    fn(new Event("DOMContentLoaded"));
    return;
  }
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

  // Manage the Bootstrap modal when using HTMX
  // Based on https://blog.benoitblanchon.fr/django-htmx-modal-form/
  htmx.on("htmx:beforeSwap", (e) => {
    // Check if the modal should be static
    let staticModal = false;
    if (e.detail.target.id == "htmx-dialog" && e.detail.xhr.response) {
      const doc = new DOMParser().parseFromString(
        e.detail.xhr.response,
        "text/html"
      );
      if (
        doc.querySelector(".modal-content").hasAttribute("data-dialog-static")
      ) {
        staticModal = true;
      }
    }

    const modal = bootstrap.Modal.getOrCreateInstance("#htmx-modal", {
      backdrop: staticModal ? "static" : true,
    });

    // An empty response targeting the #dialog does hide the modal
    if (e.detail.target.id == "htmx-dialog" && !e.detail.xhr.response) {
      modal.hide();
      e.detail.shouldSwap = false;
    }
  });
  htmx.on("htmx:afterSwap", (e) => {
    const modal = bootstrap.Modal.getInstance("#htmx-modal");
    const modalEl = document.getElementById("htmx-modal");
    modalEl.addEventListener("shown.bs.modal", (event) => {
      /** @type {HTMLInputElement} */
      const inputEl = modalEl.querySelector("input:not([type=hidden])");
      if (inputEl) {
        inputEl.focus();
      }

      if (!inputEl) {
        /** @type {HTMLTextAreaElement} */
        const textareaEl = modalEl.querySelector("textarea:not([type=hidden])");
        if (textareaEl) {
          textareaEl.focus();
          setTimeout(function () {
            textareaEl.selectionStart = textareaEl.selectionEnd = 10000;
          }, 0);
        }
      }
    });

    if (e.detail.target.id == "htmx-dialog") {
      modal.show();
    }
  });
  htmx.on("#htmx-modal", "hidden.bs.modal", () => {
    // Reset the dialog after it was closed
    document.getElementById("htmx-dialog").innerHTML = "";

    // Explicitly dispose it that next time it can be recreated
    // static or non static dynamically
    bootstrap.Modal.getInstance("#htmx-modal").dispose();
  });

  // Allow to trigger toasts from HTMX responses using HX-Trigger
  // (e.g. by using django_htmx.http.trigger_client_event)
  document.body.addEventListener("toast", (/** @type {CustomEvent} */ e) => {
    const { level, title, text } = e.detail;
    showToast(level, title, text);
  });
});

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

  const request = new Request(url, {
    method: "POST",
    headers: { "X-CSRFToken": window.public.csrf_token },
    mode: "same-origin", // Do not send CSRF token to another domain.
    body: formData,
  });

  fetch(request).then(function () {
    if (window.public.debug) {
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
    // listened by common/_toasts_panel.html
    new CustomEvent("common:add-toast", {
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
