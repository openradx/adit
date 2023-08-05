const SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED =
  "selective_transfer_advanced_options_collapsed";

function selectiveTransferForm() {
  return {
    isDestinationFolder: false,

    init: function (formEl) {
      this.formEl = formEl;

      const advancedOptionsEl = this.formEl.querySelector("#advanced_options");
      $(advancedOptionsEl).on("hide.bs.collapse", function () {
        updateSession("selective-transfer", {
          [SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED]: true,
        });
      });
      $(advancedOptionsEl).on("show.bs.collapse", function () {
        updateSession("selective-transfer", {
          [SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED]: false,
        });
      });
    },
    onStartTransfer: function (event) {
      const formEl = this.formEl;
      const buttonEl = event.currentTarget;
      buttonEl.style.pointerEvents = "none";

      function disableTransferButton() {
        // We can only disable the button after the message was send as otherwise
        // htmx won't send the message.
        buttonEl.disabled = true;
        formEl.removeEventListener("htmx:wsAfterSend", disableTransferButton);
      }
      formEl.addEventListener("htmx:wsAfterSend", disableTransferButton);
    },
  };
}
