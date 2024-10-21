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
    isDropping: false,
    buttonVisible: false,
    stopUploadButtonVisible: false,
    fileCount: 0,
    droppedFiles: [],
    uploadResultText: "",
    stopUploadVar: false,
    pbVisible: false,
    uploadCompleteTextVisible: false,

    initUploadForm: function (destEl) {
      document.body.addEventListener("chooseFolder", (e) => {
        this.chooseFolder();
      });
      const button = formEl.querySelector("button#uploadButton");
      this.stopUploadVar = false;
      this.stopUploadButtonVisible = false;
      this.fileCount = 0;
      // Add an event listener to the button
      button.addEventListener("click", function () {
        // Trigger the form submission when the button is clicked
        const myForm = formEl.querySelector("form#myForm");
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
      const inputElement = formEl.querySelector("#fileselector");

      if (!(inputElement instanceof HTMLInputElement)) {
        throw new Error(
          "inputElement must be an instance of HTMLProgressElement"
        );
      }

      if (inputElement.files.length > 0) {
        return inputElement.files;
      }

      return this.droppedFiles;
    },

    toggleUploadButtonVisibility: function () {
      // Check if files are selected
      const files = this.getFiles();
      this.buttonVisible = files.length > 0;
      this.fileCount = files.length;
      this.uploadCompleteTextVisible = false;
    },
    clearFiles: function () {
      const inputEl = formEl.querySelector("#fileselector");

      if (!(inputEl instanceof HTMLInputElement)) {
        throw new Error("inputEl must be an instance of HTMLInputElement");
      }
      inputEl.value = null;
      this.droppedFiles = [];
      this.toggleUploadButtonVisibility();
    },

    fileHandler: async (fileObj, datasets) => {
      const arrayBuffer = await fileObj.arrayBuffer();
      datasets.push(arrayBuffer);
    },

    chooseFolder: function () {
      const files = this.getFiles();
      this.loadFiles(files);
    },

    loadFiles: async function (files) {
      const destinationSelect = formEl.querySelector('[name="destination"]');

      if (!(destinationSelect instanceof HTMLSelectElement)) {
        throw new Error(
          "destinationSelect must be an instance of HTMLSelectElement"
        );
      }
      destinationSelect.options[0];
      const selectedOption =
        destinationSelect.options[destinationSelect.selectedIndex];
      const node_id = selectedOption.dataset.node_id;

      if (files.length === 0) {
        showToast("warning", "Sandbox", `No files selected.${files}`);
      } else {
        const datasets = [];
        for (const fileEntry of files) {
          await this.fileHandler(fileEntry, datasets);
        }

        let status = 0;
        let loadedFiles = 0;

        try {
          const checker = await this.isValidSeries(datasets);

          if (checker) {
            const anon = this.createAnonymizer();

            this.buttonVisible = false;
            this.stopUploadVar = false;

            const progBar = formEl.querySelector('[id="pb"]');
            if (!(progBar instanceof HTMLProgressElement)) {
              throw new Error(
                "progBar must be an instance of HTMLProgressElement"
              );
            }
            progBar.value = 0;
            this.pbVisible = true;
            for (const set of datasets) {
              // Anonymize data and write back to bufferstream
              const dicomData = dcmjs.data.DicomMessage.readFile(set, {
                ignoreErrors: true,
              });
              const pseudonym = formEl.querySelector('[name="pseudonym"]');

              if (!(pseudonym instanceof HTMLInputElement)) {
                throw new Error(
                  "pseudonym must be an instance of HTMLInputElement"
                );
              }
              let newPatientID = pseudonym.value;

              await anon.anonymize(dicomData);
              dicomData.upsertTag("00100020", "LO", [newPatientID]); // replace PatientID
              dicomData.upsertTag("00100010", "PN", [
                { Alphabetic: newPatientID },
              ]); // replace PatientName
              const anonymized_set = await dicomData.write();

              this.stopUploadButtonVisible = true;
              if (this.stopUploadVar) {
                // Stop uploading if stop button is clicked
                break;
              }

              // Upload data to server
              status = await uploadData({
                dataset: anonymized_set,
                node_id: node_id,
              });

              if (status == 200) {
                loadedFiles += 1;

                progBar.value = (loadedFiles / datasets.length) * 100;
              } else {
                this.uploadResultText = "Upload Failed";
                this.pbVisible = false;
                this.uploadCompleteTextVisible = true;
                this.stopUploadButtonVisible = false;
                break;
              }
            }
            if (loadedFiles == datasets.length) {
              this.finishUploadComplete();
            } else {
              this.finishUploadIncomplete();
            }
          } else {
            this.uploadResultText = "Upload refused - Incorrect dataset";
            this.buttonVisible = false;
            this.uploadCompleteTextVisible = true;
          }
        } catch (e) {
          this.uploadResultText = "Upload Failed due to an Error";
          this.buttonVisible = false;
          this.uploadCompleteTextVisible = true;
          console.error(e);
        }
      }
    },

    finishUploadComplete: function () {
      this.uploadResultText = "Upload Successful!";
      this.stopUploadButtonVisible = false;
      this.pbVisible = false;
      this.uploadCompleteTextVisible = true;

      setTimeout(() => {
        this.uploadCompleteTextVisible = false;
      }, 5000);
    },

    stopUpload: function () {
      this.stopUploadVar = true;
      this.stopUploadButtonVisible = false;

      this.finishUploadIncomplete();
    },

    finishUploadIncomplete: function () {
      if (this.stopUploadVar) {
        this.uploadResultText = "Upload Cancelled";
      } else {
        this.uploadResultText = "Upload Failed";
      }
      this.stopUploadButtonVisible = false;
      this.pbVisible = false;
      this.uploadCompleteTextVisible = true;

      setTimeout(() => {
        this.uploadCompleteTextVisible = false;
      }, 5000);
    },

    createAnonymizer: () => {
      const seedElement = document.getElementById("anon-seed-json");
      if (!seedElement) {
        throw new Error("anon-seed-json element does not exist");
      }
      const seedText = seedElement.textContent;
      if (!seedText) {
        throw new Error("anon-seed-json element is empty");
      }
      const seed = JSON.parse(seedText);

      return new Anonymizer({ seed: seed });
    },

    traverseDirectory: async function (item, files) {
      if (item.isFile) {
        const file = await new Promise((resolve, reject) => {
          item.file(resolve, reject);
        });
        files.push(file);
      } else {
        const directoryReader = item.createReader();
        const items = await new Promise((reslove, reject) => {
          directoryReader.readEntries(reslove, reject);
        });

        for (let item of items) {
          await this.traverseDirectory(item, files);
        }
      }
    },

    handleDrop: async function (ev) {
      const files = [];
      this.uploadCompleteTextVisible = false;
      const items = ev.dataTransfer.items;

      for (const item of items) {
        const itemEntry = item.webkitGetAsEntry();
        if (itemEntry) {
          await this.traverseDirectory(itemEntry, files);
        }
      }

      this.fileCount = files.length;

      if (files.length > 0) {
        const inputElement = document.getElementById("fileselector");

        if (inputElement instanceof HTMLInputElement) {
          inputElement.value = null;
        }

        this.buttonVisible = true;
        this.droppedFiles = files;
      }
    },

    isValidSeries: (datasets) => {
      const patientIDs = new Set();
      const patientBirthdates = new Set();
      const patientNames = new Set();

      for (const set of datasets) {
        const patIDTagNumber = "00100020";
        const patNameTagNumber = "00100010";
        const patBirthdateTagNumber = "00100030";

        const dcm = dcmjs.data.DicomMessage.readFile(set, {
          ignoreErrors: true,
        });

        const patientID = dcm.dict[patIDTagNumber]?.Value[0];
        if (patientID != null) {
          patientIDs.add(patientID);
        }

        const patientName = dcm.dict[patNameTagNumber]?.Value[0]?.Alphabetic;
        if (patientName != null) {
          patientNames.add(patientName);
        }

        const patientBirthdate = dcm.dict[patBirthdateTagNumber]?.Value[0];
        if (patientBirthdate != null) {
          patientBirthdates.add(patientBirthdate);
        }
      }

      // Check if in a whole study are more than one PatientID, Name or Birthdate
      return (
        patientIDs.size == 1 &&
        patientNames.size == 1 &&
        patientBirthdates.size == 1
      );
    },
  };
}

const uploadData = async (data) => {
  const formData = new FormData();
  for (const key in data) {
    const blob = new Blob([data[key]]);
    formData.append(key, blob);
  }

  const url = `/upload/data-upload/${data.node_id}/`;

  const request = new Request(url, {
    method: "POST",
    headers: { "X-CSRFToken": window.public.csrf_token },
    mode: "same-origin", // Do not send CSRF token to another domain.
    body: formData,
  });
  let status = 0;

  return fetch(request)
    .then(async (response) => {
      const text = await response.text();

      return response.ok ? response.status : Promise.reject(new Error(text));
    })
    .catch((error) => {
      console.error(`Error: ${error.message || "Network error"}`);
      return 500;
    });
};
