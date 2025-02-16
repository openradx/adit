"use strict";

// Keep those variables in sync with the ones in the Django view
const BATCH_QUERY_SOURCE = "batch_query_source";
const BATCH_QUERY_URGENT = "batch_query_urgent";
const BATCH_QUERY_SEND_FINISHED_MAIL = "batch_query_send_finished_mail";

function batchQueryJobForm() {
  return {
    onSourceChange: function (ev) {
      updatePreferences("batch-query", {
        [BATCH_QUERY_SOURCE]: ev.target.value,
      });
    },
    onUrgentChange: function (ev) {
      updatePreferences("batch-query", {
        [BATCH_QUERY_URGENT]: ev.target.checked,
      });
    },
    onSendFinishedMailChange: function (ev) {
      updatePreferences("batch-query", {
        [BATCH_QUERY_SEND_FINISHED_MAIL]: ev.target.checked,
      });
    },
  };
}
