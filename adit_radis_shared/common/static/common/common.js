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
 * Add a new toast to the toasts panel by dispatching a custom event
 * that is listened by the toasts panel.
 *
 * @param {("success"|"warning"|"error")} level
 * @param {string} title
 * @param {string} text
 * @returns {void}
 */
function showToast(level, title, text) {
  window.dispatchEvent(
    // listened to by common/_toasts_panel.html
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
 * @returns {object} Alpine data model
 */
function ToastsPanel() {
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
    currentId: 1,
    options: {
      duration: 30000, // 30 seconds
    },
    /**
     * An array of toasts created by the client.
     * @type{Array}
     * @property {number} id
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
    showToast: function (toastEl) {
      new bootstrap.Toast(toastEl, {
        delay: this.options.duration,
      }).show();
    },
    /**
     * Add a toast to the toasts list. Call the showToast function above to
     * add toasts to the list from another function or script.
     * @param {CustomEvent<{level: "success"|"warning"|"error", title: string, text: string}>} evt
     * @returns {void}
     */
    addToast: function (evt) {
      this.toasts.unshift({
        id: this.currentId++,
        level: evt.detail.level,
        title: capitalize(evt.detail.title),
        text: evt.detail.text,
      });
    },
  };
}
