ready(function () {
  showMessage("success", "Sandbox", "This message is Javascript generated!");
});

function sandbox() {
  return {
    buttonClicked: function () {
      showMessage("warning", "Sandbox", "You clicked a button!");
    },
  };
}
