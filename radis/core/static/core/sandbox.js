$(function () {
  window.dispatchEvent(
    new CustomEvent("core:add-message", {
      detail: {
        level: "success",
        title: "Aloha",
        text: "This message is Javascript generated!",
      },
    })
  );
});

function sandbox() {
  return {
    buttonClicked: function ($dispatch) {
      $dispatch("core:add-message", {
        level: "warning", // possible values are success, warning, error or null
        title: "Sandbox",
        text: "You clicked a button!",
      });
    },
  };
}
