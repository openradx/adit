"use strict";

/**
 * Alpine data model for token authentication
 * @returns {object} Alpine data model
 */
function newToken() {
  return {
    /**
     * Copy the token to the clipboard.
     * @param {string} token
     * @returns {void}
     */
    copyTokenToClipboard: function (token) {
      navigator.clipboard.writeText(token);
      showToast("success", "Clipboard", "Copied token to clipboard!");
    },
  };
}
