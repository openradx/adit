function newToken() {
  return {
    copyTokenToClipboard: function (token) {
      navigator.clipboard.writeText(token);
      showMessage("success", "Clipboard", "Copied token to clipboard!");
    },
  };
}
