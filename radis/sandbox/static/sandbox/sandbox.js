"use strict";

function toastSandbox() {
  return {
    buttonClicked: function () {
      showToast("warning", "Sandbox", "You clicked a button!");
    },
  };
}
