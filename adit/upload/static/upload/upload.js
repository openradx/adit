"use strict";
// import * as dcmjs from "dcmjs";
// Keep those variables in sync with the ones in the Django view
const UPLOAD_DESTINATION = "upload_destination";

/**
 * Alpine.js component for the selective transfer job form.
 * @param {HTMLElement} formEl
 * @returns {object} Alpine data model
 */

function uploadJobForm(formEl) {
  return {
    initDestination: function (destEl) {
      this._updateIsDestinationFolder(destEl);
    },
    onDestinationChange: function (ev) {
      this._updateIsDestinationFolder(ev.target);

      updatePreferences("upload", {
        [UPLOAD_DESTINATION]: ev.target.value,
      });
    },
    _updateIsDestinationFolder: function (destEl) {
      const option = destEl.options[destEl.selectedIndex];
      this.isDestinationFolder = option.dataset.node_type === "folder";
    },
    query4Folder: function () {
      const pseudonymInput = formEl.querySelector('[name="pseudonym"]');
      const Path = formEl.querySelector('[name="data_folder_path"]');
      if (
        pseudonymInput instanceof HTMLInputElement &&
        Path instanceof HTMLInputElement
      ) {
        const pseudonymValue = pseudonymInput.value + Path.value;
        showToast("warning", "Sandbox", `Pseudonym: ${pseudonymValue}`);
        console.log("Hallo");
      }
    },

    chooseFolder: function () {
      const folderPath = formEl.querySelector('[name="data_folder_path"]');

      var inputElement = document.getElementById("fileselector");

      if (inputElement instanceof HTMLInputElement) {
        var files = inputElement.files;
      }
      if (files.length === 0) {
        showToast("warning", "Sandbox", `No files selected.${files}`);
      } else {
        showToast("warning", "Sandbox", `We have ${files.length} files!!!`);
        var i = 0;
        for (const file of files) {
          // showToast("warning", "Sandbox", `No#${i}: ${files[i].name}!!!`);
          const fileReader = new FileReader();
          fileReader.onload = (function (file) {
            return function (e) {
              uploadData({
                ["file_data"]: file.name,
              });
              const arrayBuffer = fileReader.result;
              const myDict = dcmjs.data.DicomMessage.readFile(arrayBuffer);
              const tag = myDict.dict["00080060"].Value[0];
              // showToast(
              //   "warning",
              //   "Sandbox",
              //   `Modality of ${file.name}: ${tag}!!!`
              // );

              // Use the myDict object here
            };
          })(file);
          fileReader.readAsArrayBuffer(file);
          i++;
        }
      }

      // Use the File System Access API to allow the user to choose a directory
      //const directoryHandle = await window.showDirectoryPicker();

      // Get the absolute path from the directory handle
      //const folderPath = directoryHandle.name;

      // Update the data_folder_path field
      const dataFolderPathInput = formEl.querySelector(
        '[name="data_folder_path"]'
      );
      if (dataFolderPathInput instanceof HTMLInputElement) {
        dataFolderPathInput.value = "abc"; //files[0].name;
      } else {
        console.error(
          "folder_path input element not found or is not an HTMLInputElement"
        );
      }
      // } catch (error) {
      //   showToast("warning", "Sandbox",`"Error choosing folde:", ${error}`);
      // }
    },
  };
}
