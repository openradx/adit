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
    pbStyleDisplay: String,
    uploadCompleteTextStyleDisplay: String,
    stopUploadButtonStyleDisplay: String,

    initUploadForm: function (destEl) {
      document.body.addEventListener("chooseFolder", (e) => {
        this.chooseFolder();
      });
      var button = formEl.querySelector("button#uploadButton");

      // Add an event listener to the button
      button.addEventListener("click", function () {
        // Trigger the form submission when the button is clicked
        var myForm = formEl.querySelector("form#myForm");
        if (myForm instanceof HTMLFormElement) {
          htmx.trigger("#myForm", "submit");
        }
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
      var inputElement = formEl.querySelector("#fileselector");
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
      this.uploadCompleteTextStyleDisplay = "none"; //TODO: introduce variable to change classe state, don't change html directly -> https://alpinejs.dev/directives/bind
    },
    clearFiles: function () {
      var inputEl = formEl.querySelector("#fileselector");

      if (inputEl instanceof HTMLInputElement) {
        inputEl.value = null;
      }
      this.droppedFiles = [];
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
        var node_id = selectedOption.getAttribute("data-node_id");
        console.log(node_id);
      }
      console.log(node_id);
      if (files.length === 0) {
        showToast("warning", "Sandbox", `No files selected.${files}`);
      } else {
        var datasets = [];
        for (const fileEntry of files) {
          await this.fileHandler(fileEntry, datasets);
        }

        let status = 0;
        let loadedFiles = 0;

        try {
          const checker = await this.checkPatientIDs(datasets);

          if (checker) {
            const anon = this.createAnonymizer();

            this.buttonVisible = false;
            this.stopUploadVar = false;

            for (const set of datasets) {
              // Anonymize data and write back to bufferstream
              const dicomData = dcmjs.data.DicomMessage.readFile(set, {
                ignoreErrors: true,
              });

              await anon.anonymize(dicomData);
              const anonymized_set = await dicomData.write();

              this.pbStyleDisplay = "inline-block";
              this.stopUploadButtonStyleDisplay = "inline-block";

              if (this.stopUploadVar) {
                // Stop uploading if stop button is clicked
                break;
              }

              // Upload data to server
              status = await uploadData({
                ["dataset"]: anonymized_set,
                ["node_id"]: node_id,
              });

              if (status == 200) {
                loadedFiles += 1;
                const progBar = formEl.querySelector('[name="pb"]');
                // document.getElementById("pb");
                if (progBar instanceof HTMLProgressElement) {
                  progBar.value = (loadedFiles / datasets.length) * 100;
                }
              } else {
                this.uploadResultText = "Upload Failed";
                this.pbStyleDisplay = "none";
                this.uploadCompleteTextStyleDisplay = "inline-block";
                break;
              }
            }
            if (loadedFiles == datasets.length) {
              this.uploadSuccessfull();
            } else {
              this.stopUpload();
            }
          } else {
            this.uploadResultText = "Upload refused - Fehlerhafte Datensätze";
            this.buttonVisible = false;
            this.uploadCompleteTextStyleDisplay = "inline-block";
          }
        } catch (e) {
          this.uploadResultText = "Upload Failed due to an Error";
          console.log(e);
          this.uploadCompleteTextStyleDisplay = "inline-block";
        }

        console.info("Upload process finished successfully.");
      }
    },

    uploadSuccessfull: function () {
      this.uploadResultText = "Upload Successful!";

      setTimeout(function () {
        this.pbStyleDisplay = "none";
      }, 3000);

      setTimeout(function () {
        this.stopUploadButtonStyleDisplay = "none";
      }, 500);

      setTimeout(function () {
        this.uploadCompleteTextStyleDisplay = "inline-block";
      }, 3000);
    },

    stopUpload: function () {
      this.stopUploadButtonStyleDisplay = "none";

      if (this.stopUploadVar) {
        this.uploadResultText = "Upload Cancelled";
      } else {
        this.uploadResultText = "Upload Failed";
      }

      this.pbStyleDisplay = "none";
      this.uploadCompleteTextStyleDisplay = "inline-block";
    },

    createAnonymizer: function () {
      const pseudonym = formEl.querySelector('[name="pseudonym"]');
      var newPatientID = "";
      if (pseudonym instanceof HTMLInputElement) {
        newPatientID = pseudonym.value;
      }

      const anon = new Anonymizer(
        newPatientID,
        undefined,
        undefined,
        undefined,
        undefined,
        123456789
      );

      return anon;
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
      this.uploadCompleteTextStyleDisplay = "none";

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
    },

    checkPatientIDs: async function (datasets) {
      const patientIDs = new Set();
      const patientBirthdates = new Set();
      const patientNames = new Set();

      try {
        for (const set of datasets) {
          const dcm = dcmjs.data.DicomMessage.readFile(set, {
            ignoreErrors: true,
          });

          try {
            patientIDs.add(dcm.dict["00100020"].Value[0]); // Patient ID
          } catch (e) {
            console.log("Missing PatientID"); //TODO:
          }
          try {
            patientNames.add(dcm.dict["00100010"].Value[0].Alphabetic); // Patient Name
          } catch (e) {
            console.log("Missing PatientName"); //TODO:
          }
          try {
            patientBirthdates.add(dcm.dict["00100030"].Value[0]); // Patient Birthdate
          } catch (e) {
            console.log("Missing PatientBirthdate"); //TODO:
          }
        }
        // Check if in a whole study are more than one PatientID, Name or Birthdate

        return (
          patientIDs.size <= 1 &&
          patientNames.size <= 1 &&
          patientBirthdates.size <= 1
        );
      } catch (e) {
        console.log(e); //TODO:
        return false;
      }
    },
  };
}

async function uploadData(data) {
  const formData = new FormData();
  for (const key in data) {
    const blob = new Blob([data[key]]);
    formData.append(key, blob);
  }
  console.log(data.node_id);
  const url = `/upload/data-upload/${data.node_id}/`;

  const request = new Request(url, {
    method: "POST",
    headers: { "X-CSRFToken": window.public.csrf_token },
    mode: "same-origin", // Do not send CSRF token to another domain.
    body: formData,
  });
  var status = 0;
  return fetch(request)
    .then(async function (response) {
      if (window.public.debug) {
        const text = await response.text();
        if (response.ok) {
          console.log(
            "Uploaded data to server with status:",
            text,
            response.status
          ); //TODO:

          return response.status;
        } else {
          console.log("Response from server:", text); //TODO:
        }
      }
    })
    .catch(function (error) {
      console.log(`Error: ${error.reason_phrase}`); //TODO:
      return 0;
    });
}
