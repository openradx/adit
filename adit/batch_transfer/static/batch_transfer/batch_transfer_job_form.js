// Keep those variables in sync with the ones in the Django view
const BATCH_TRANSFER_SOURCE = "batch_transfer_source";
const BATCH_TRANSFER_DESTINATION = "batch_transfer_destination";
const BATCH_TRANSFER_URGENT = "batch_transfer_urgent";
const BATCH_TRANSFER_SEND_FINISHED_MAIL = "batch_transfer_send_finished_mail";

function batchTransferJobForm() {
  return {
    onSourceChange: function (ev) {
      updatePreferences("batch-transfer", {
        [BATCH_TRANSFER_SOURCE]: ev.target.value,
      });
    },
    onDestinationChange: function (ev) {
      updatePreferences("batch-transfer", {
        [BATCH_TRANSFER_DESTINATION]: ev.target.value,
      });
    },
    onUrgentChange: function (ev) {
      updatePreferences("batch-transfer", {
        [BATCH_TRANSFER_URGENT]: ev.target.checked,
      });
    },
    onSendFinishedMailChange: function (ev) {
      updatePreferences("batch-transfer", {
        [BATCH_TRANSFER_SEND_FINISHED_MAIL]: ev.target.checked,
      });
    },
  };
}
