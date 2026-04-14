"use strict";

// Keep those variables in sync with the ones in the Django view
const MASS_TRANSFER_SOURCE = "mass_transfer_source";
const MASS_TRANSFER_DESTINATION = "mass_transfer_destination";
const MASS_TRANSFER_GRANULARITY = "mass_transfer_granularity";
const MASS_TRANSFER_SEND_FINISHED_MAIL = "mass_transfer_send_finished_mail";

function massTransferJobForm() {
  return {
    pseudonymize:
      /** @type {HTMLInputElement | null} */ (
        document.getElementById("id_pseudonymize")
      )?.checked ?? true,
    isDestinationFolder: true,
    get showSalt() {
      return this.pseudonymize;
    },
    initDestination: function (destEl) {
      this._updateIsDestinationFolder(destEl);
    },
    onSourceChange: function (ev) {
      updatePreferences("mass-transfer", {
        [MASS_TRANSFER_SOURCE]: ev.target.value,
      });
    },
    onDestinationChange: function (ev) {
      this._updateIsDestinationFolder(ev.target);
      updatePreferences("mass-transfer", {
        [MASS_TRANSFER_DESTINATION]: ev.target.value,
      });
    },
    onGranularityChange: function (ev) {
      updatePreferences("mass-transfer", {
        [MASS_TRANSFER_GRANULARITY]: ev.target.value,
      });
    },
    onSendFinishedMailChange: function (ev) {
      updatePreferences("mass-transfer", {
        [MASS_TRANSFER_SEND_FINISHED_MAIL]: ev.target.checked,
      });
    },
    _updateIsDestinationFolder: function (destEl) {
      const idx = destEl.selectedIndex;
      if (idx < 0) {
        this.isDestinationFolder = true;
        return;
      }
      const option = destEl.options[idx];
      this.isDestinationFolder = option?.dataset.node_type === "folder";
    },
  };
}

// JSON editor is now handled by CodeMirror in the form template.
