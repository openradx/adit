"use strict";

// Keep those variables in sync with the ones in the Django view
const SELECTIVE_TRANSFER_SOURCE = "selective_transfer_source";
const SELECTIVE_TRANSFER_DESTINATION = "selective_transfer_destination";
const SELECTIVE_TRANSFER_URGENT = "selective_transfer_urgent";
const SELECTIVE_TRANSFER_SEND_FINISHED_MAIL =
  "selective_transfer_send_finished_mail";
const SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED =
  "selective_transfer_advanced_options_collapsed";

/**
 * Alpine.js component for the selective transfer job form.
 * @param {HTMLElement} formEl
 * @returns {object} Alpine data model
 */
function selectiveTransferJobForm(formEl) {
  return {
    isDestinationFolder: false,

    init: function () {
      // We can't directly listen to the change with Alpine, but have to use
      // the Bootstrap events
      const advancedOptionsEl = formEl.querySelector("#advanced_options");
      advancedOptionsEl.addEventListener("hide.bs.collapse", function () {
        updatePreferences("selective-transfer", {
          [SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED]: true,
        });
      });
      advancedOptionsEl.addEventListener("show.bs.collapse", function () {
        updatePreferences("selective-transfer", {
          [SELECTIVE_TRANSFER_ADVANCED_OPTIONS_COLLAPSED]: false,
        });
      });
    },

    initDestination: function (destEl) {
      this._updateIsDestinationFolder(destEl);
    },

    onSourceChange: function (ev) {
      this._resetQueryResults();

      updatePreferences("selective-transfer", {
        [SELECTIVE_TRANSFER_SOURCE]: ev.target.value,
      });
    },

    onDestinationChange: function (ev) {
      this._updateIsDestinationFolder(ev.target);

      updatePreferences("selective-transfer", {
        [SELECTIVE_TRANSFER_DESTINATION]: ev.target.value,
      });
    },

    onUrgentChange: function (ev) {
      updatePreferences("selective-transfer", {
        [SELECTIVE_TRANSFER_URGENT]: ev.target.checked,
      });
    },

    onSendFinishedMailChange: function (ev) {
      updatePreferences("selective-transfer", {
        [SELECTIVE_TRANSFER_SEND_FINISHED_MAIL]: ev.target.checked,
      });
    },

    onStartTransfer: function (event) {
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

    onArchivePasswordChange: function (ev) {
      console.log("Archive password changed to:", ev.target.value); // Debug statement
      const niftiCheckbox = formEl.querySelector("[name=convert_to_nifti]");
      if (ev.target.value) {
        niftiCheckbox.checked = false; // Uncheck NIfTI conversion
        updatePreferences("selective-transfer", {
          convert_to_nifti: false,
        });
      }
    },

    onConvertToNiftiChange: function (ev) {
      const archivePasswordField = formEl.querySelector(
        "[name=archive_password]"
      );
      console.log("Archive password field:", archivePasswordField); // Debug statement

      if (ev.target.checked) {
        archivePasswordField.value = ""; // Clear archive password
        archivePasswordField.disabled = true; // Disable archive password field
        updatePreferences("selective-transfer", {
          archive_password: "",
          archive_password_disabled: true,
        });
      } else {
        archivePasswordField.disabled = false; // Enable archive password field
        updatePreferences("selective-transfer", {
          archive_password_disabled: false,
        });
      }
    },

    _updateIsDestinationFolder: function (destEl) {
      const option = destEl.options[destEl.selectedIndex];
      this.isDestinationFolder = option.dataset.node_type === "folder";
    },

    _resetQueryResults: function () {
      const resetButtonEl = formEl.querySelector("[value=reset]");
      // @ts-ignore
      resetButtonEl.click();
    },
  };
}
