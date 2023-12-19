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
    isDropping: Boolean,
    buttonVisible: Boolean,
    fileCount: 0,
    droppedFiles: Object,

    getFiles: function () {
      var inputElement = document.getElementById("fileselector");
      if (
        inputElement instanceof HTMLInputElement &&
        inputElement.files.length > 0
      ) {
        return inputElement.files;
      } else if (this.droppedFiles.length > 0) {
        const files = [];
        for (const f of this.droppedFiles) {
          files.push(f);
        }
        return files;
      } else {
        return [];
      }
    },

    toggleUploadButtonVisibility: function () {
      // Check if files are selected
      const files = this.getFiles();
      this.buttonVisible = files.length > 0;
      this.fileCount = files.length;
    },
    clearFiles: function () {
      var inputEl = document.getElementById("fileselector");

      if (inputEl instanceof HTMLInputElement) {
        inputEl.value = null;
      }
      this.droppedFiles = [];
      console.log(inputEl);
      this.toggleUploadButtonVisibility();
    },
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

    fileHandler: async function (fileObj, datasets) {
      const arrayBuffer = await fileObj.arrayBuffer(); //await fileReader.readAsArrayBuffer(fileObj);
      datasets.push(arrayBuffer);
      console.log(datasets);
    },

    chooseFolder: function () {
      const files = this.getFiles();
      console.log(files);
      this.loadFiles(files);
    },

    loadFiles: async function (files) {
      const destinationSelect = formEl.querySelector('[name="destination"]');
      if (destinationSelect instanceof HTMLSelectElement) {
        const selectedOption =
          destinationSelect.options[destinationSelect.selectedIndex];
        var node_id = selectedOption.getAttribute("node_id");
      }
      showToast("warning", "Sandbox", "Let's upload some Files!!!");
      if (files.length === 0) {
        showToast("warning", "Sandbox", `No files selected.${files}`);
      } else {
        showToast("warning", "Sandbox", `We have ${files.length} files!!!`);

        var datasets = [];
        for (const fileEntry of files) {
          await this.fileHandler(fileEntry, datasets);
        }
        if (this.checkPatientIDs(datasets)) {
          for (const set in datasets) {
            console.log("lets upload");
            uploadData({
              ["dataset"]: set,
              ["node_id"]: node_id,
            });
          }
        } else {
          console.log("Not same PatientIDs");
        }
      }
    },

    retrieveFilefromFileEntry: async function (fileEntry) {
      return new Promise(fileEntry.file.bind(fileEntry));
    },

    readDirectory: function (item) {
      const directoryReader = item.createReader();
      return new Promise(directoryReader.readEntries.bind(directoryReader));
    },

    traverseDirectory: async function (item, files) {
      if (item.isFile) {
        const file = await this.retrieveFilefromFileEntry(item, files);
        files.push(file);
      } else {
        const items = await this.readDirectory(item);
        for (let item of items) {
          await this.traverseDirectory(item, files);
        }
      }
    },

    handleDrop: async function (ev) {
      const files = [];
      let promiseList = [];
      const items = ev.dataTransfer.items;
      for (const item of items) {
        const itemEntry = item.webkitGetAsEntry();
        if (itemEntry) {
          await this.traverseDirectory(itemEntry, files);
        }
      }
      console.log(files);
      console.log(`We've got all files: ${files}`);
      this.fileCount = files.length;
      console.log(`The FileArray: ${files}`);
      // Hier gehts dann mit dem eigentlichen Upload los

      if (files.length > 0) {
        var inputElement = document.getElementById("fileselector");

        if (inputElement instanceof HTMLInputElement) {
          inputElement.value = null;
        }

        this.buttonVisible = true;
        this.droppedFiles = files;
      }
      console.log(this.droppedFiles);
    },

    checkPatientIDs: function (datasets) {
      const patientIDs = new Set();
      const patientBirthdates = new Set();
      const patientNames = new Set();

      for (const set of datasets) {
        // const dcm = dcmjs.data.DicomMessage.readFile(set);
        // patientIDs.add(dcm.dict["00100020"].Value[0]);
        // patientNames.add(dcm.dict["00100010"].Value[0]);
        // patientBirthdates.add(dcm.dict["00100030"].Value[0]);
      }

      console.log(patientIDs);

      return (
        patientIDs.size == 1 &&
        patientNames.size == 1 &&
        patientBirthdates.size == 1
      );
    },
  };
}
