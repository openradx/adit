const SELECTIVE_TRANSFER_SOURCE = "selective_transfer_source";
const SELECTIVE_TRANSFER_DESTINATION = "selective_transfer_destination";
const SELECTIVE_TRANSFER_URGENT = "selective_transfer_urgent";
const SELECTIVE_TRANSFER_SEND_FINISHED_MAIL =
  "selective_transfer_send_finished_mail";
const SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED =
  "selective_transfer_advanced_options_collapsed";

function selectiveTransferForm() {
  return {
    isDestinationFolder: false,

    init: function (formEl) {
      this.formEl = formEl;

      // Retain source
      const sourceInputEl = this.formEl.querySelector("#id_source");
      sourceInputEl.addEventListener("change", function (e) {
        sourceId = e.target.value;
        updateSession("selective-transfer", {
          [SELECTIVE_TRANSFER_SOURCE]: sourceId,
        });
      });

      // Retain destination
      const destinationInputEl = this.formEl.querySelector("#id_destination");
      destinationInputEl.addEventListener("change", function (e) {
        destinationId = e.target.value;
        updateSession("selective-transfer", {
          [SELECTIVE_TRANSFER_DESTINATION]: destinationId,
        });
      });

      // Retain urgent
      const urgentInputEl = this.formEl.querySelector("#id_urgent");
      urgentInputEl.addEventListener("change", function (e) {
        urgent = e.target.checked;
        updateSession("selective-transfer", {
          [SELECTIVE_TRANSFER_URGENT]: urgent,
        });
      });

      // Retain send finished mail
      const sendFinishedMailInputEl = this.formEl.querySelector(
        "#id_send_finished_mail"
      );
      sendFinishedMailInputEl.addEventListener("change", function (e) {
        sendFinishedMail = e.target.checked;
        updateSession("selective-transfer", {
          [SELECTIVE_TRANSFER_SEND_FINISHED_MAIL]: sendFinishedMail,
        });
      });

      // Retain if the advanced options are collapsed
      const advancedOptionsCollapsedInputEl = this.formEl.querySelector(
        "#id_advanced_options_collapsed"
      );
      const advancedOptionsEl = this.formEl.querySelector("#advanced_options");
      advancedOptionsEl.addEventListener("hide.bs.collapse", function () {
        advancedOptionsCollapsedInputEl.value = "true";
        updateSession("selective-transfer", {
          [SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED]: true,
        });
      });
      advancedOptionsEl.addEventListener("show.bs.collapse", function () {
        advancedOptionsCollapsedInputEl.value = "false";
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
