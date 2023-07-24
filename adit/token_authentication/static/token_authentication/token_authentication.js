function newToken() {
  return {
    copyTokenToClipboard: function ($dispatch, token) {
      navigator.clipboard.writeText(token);
      $dispatch("core:add-message", {
        level: "success",
        title: "Clipboard",
        text: "Copied token to clipboard!",
      });
    },
  };
}
