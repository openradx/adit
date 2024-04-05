"use strict";

// Keep those variables in sync with the ones in the Django view
const UPLOAD_DESTINATION = "upload_destination";
/**
 * Alpine.js component for the selective transfer job form.
 * @param {HTMLElement} formEl
 * @returns {object} Alpine data model
 */

function UploadJobForm(formEl) {
  return {
    isDropping: Boolean,
    buttonVisible: Boolean,
    stopUploadButtonVisible: Boolean,
    fileCount: 0,
    droppedFiles: Object,
    uploadResultText: String,
    stopUploadVar: Boolean,

    initUploadForm: function (destEl) {
      document.body.addEventListener("chooseFolder", (e) => {
        this.chooseFolder();
      });
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
      this.buttonVisible = files.length > 0 ? true : false;
      this.fileCount = files.length;
      document.getElementById("uploadCompleteText").style.display = "none";
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

    fileHandler: async function (fileObj, datasets) {
      const arrayBuffer = await fileObj.arrayBuffer(); //await fileReader.readAsArrayBuffer(fileObj);
      datasets.push(arrayBuffer);
    },

    chooseFolder: function () {
      const files = this.getFiles();

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
        const x = dcmjs.data.DicomMessage.readFile(datasets[0]);
        console.log(x.dict["00080090"]);
        let status = 0;
        let loadedFiles = 0;
        if (this.checkPatientIDs(datasets)) {
          const anon = new Anonymizer();
          this.buttonVisible = false;
          this.stopUploadVar = false;
          for (const set of datasets) {
            console.log(this.stopUploadVar);
            document.getElementById("pb").style.display = "inline-block";
            if (this.stopUploadVar) {
              break;
            } // Stop uploading if stop button is clicked

            console.log("toBEUploaded:", set);
            status = await uploadData({
              ["dataset"]: set,
              ["node_id"]: node_id,
            });
            if (status == 200) {
              loadedFiles += 1;

              document.getElementById("stopUploadButton").style.display =
                "inline-block";
              const progBar = document.getElementById("pb");
              if (progBar instanceof HTMLProgressElement) {
                progBar.value = (loadedFiles / datasets.length) * 100;
              }
            } else {
              this.uploadResultText = "Upload Failed";
              document.getElementById("pb").style.display = "none";
              document.getElementById("uploadCompleteText").style.display =
                "inline-block";

              console.log("Upload Failed");
              break;
            }
          }
          if (loadedFiles == datasets.length) {
            this.uploadResultText = "Upload Successful!";
            document.getElementById("stopUploadButton").style.display = "none";
            setTimeout(function () {
              document.getElementById("pb").style.display = "none";
            }, 3000);

            setTimeout(function () {
              document.getElementById("uploadCompleteText").style.display =
                "inline-block";
            }, 3000);
            // Wait for 3 seconds (3000 milliseconds)
          } else {
            document.getElementById("stopUploadButton").style.display = "none";

            if (this.stopUploadVar) {
              this.uploadResultText = "Upload Cancelled";
            } else {
              this.uploadResultText = "Upload Failed";
            }

            document.getElementById("pb").style.display = "none";
            document.getElementById("uploadCompleteText").style.display =
              "inline-block";
          }
        }

        console.log("Upload process finished");
      }
    },

    stopUpload: async function () {
      this.stopUploadVar = true;
      console.log("STOP ALL UPLOADS!!!!!!!!!");
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
      document.getElementById("uploadCompleteText").style.display = "none";

      const items = ev.dataTransfer.items;
      for (const item of items) {
        const itemEntry = item.webkitGetAsEntry();
        if (itemEntry) {
          await this.traverseDirectory(itemEntry, files);
        }
      }

      this.fileCount = files.length;

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

    checkPatientIDs: async function (datasets) {
      const patientIDs = new Set();
      const patientBirthdates = new Set();
      const patientNames = new Set();

      for (const set of datasets) {
        const dcm = dcmjs.data.DicomMessage.readFile(set);

        const anon = new Anonymizer();

        await anon.anonymize(dcm);
        console.log(dcm.dict["00080090"]);
        patientIDs.add(dcm.dict["00100020"].Value[0]);
        patientNames.add(dcm.dict["00100010"].Value[0]);
        patientBirthdates.add(dcm.dict["00100030"].Value[0]);
      }
      return (
        patientIDs.size == 1 &&
        patientNames.size == 1 &&
        patientBirthdates.size == 1
      );
    },
  };
}

async function uploadData(data) {
  const formData = new FormData();
  for (const key in data) {
    const blob = new Blob([data[key]]);
    formData.append(key, blob);
  }

  const url = `/upload/data-upload/${data.node_id}/`;

  const config = getConfig();
  const request = new Request(url, {
    method: "POST",
    headers: { "X-CSRFToken": config.csrf_token },
    mode: "same-origin", // Do not send CSRF token to another domain.
    body: formData,
  });
  var status = 0;
  return fetch(request)
    .then(async function (response) {
      const config = getConfig();
      if (config.debug) {
        const text = await response.text();
        if (response.ok) {
          console.log(
            "Uploaded data to server with status:",
            text,
            response.status
          );

          return response.status;
        } else {
          console.log("Response from server:", text);
        }
      }
    })
    .catch(function (error) {
      console.log(`Error: ${error.reason_phrase}`);
      return 0;
    });
}
