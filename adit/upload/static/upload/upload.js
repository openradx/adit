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

      var button = document.getElementById("uploadButton");
      // Add an event listener to the button
      button.addEventListener("click", function () {
        // Trigger the form submission when the button is clicked
        var form = document.getElementById("myForm");
        if (form instanceof HTMLFormElement) {
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
        console.log(node_id);
      }
      console.log(node_id);
      if (files.length === 0) {
        showToast("warning", "Sandbox", `No files selected.${files}`);
      } else {
        //showToast("warning", "Sandbox", `${files.length} files selected`);

        var datasets = [];
        for (const fileEntry of files) {
          await this.fileHandler(fileEntry, datasets);
        }

        let status = 0;
        let loadedFiles = 0;
        try {
          const checker = await this.checkPatientIDs(datasets);
          if (checker) {
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
            this.buttonVisible = false;
            this.stopUploadVar = false;
            for (const set of datasets) {
              // Anonymize data and write back to bufferstream
              const x = dcmjs.data.DicomMessage.readFile(set, {
                ignoreErrors: true,
              });
              const y = dcmjs.data.DicomMessage.readFile(set, {
                ignoreErrors: true,
              });

              await anon.anonymize(x);
              const anonymized_set = await x.write();

              document.getElementById("pb").style.display = "inline-block";
              document.getElementById("stopUploadButton").style.display =
                "inline-block";
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

              setTimeout(function () {
                document.getElementById("pb").style.display = "none";
              }, 3000);
              setTimeout(function () {
                document.getElementById("stopUploadButton").style.display =
                  "none";
              }, 500);

              setTimeout(function () {
                document.getElementById("uploadCompleteText").style.display =
                  "inline-block";
              }, 3000);
              // Wait for 3 seconds (3000 milliseconds)
            } else {
              document.getElementById("stopUploadButton").style.display =
                "none";

              if (this.stopUploadVar) {
                this.uploadResultText = "Upload Cancelled";
              } else {
                this.uploadResultText = "Upload Failed";
              }

              document.getElementById("pb").style.display = "none";
              document.getElementById("uploadCompleteText").style.display =
                "inline-block";
            }
          } else {
            this.uploadResultText = "Upload refused - Fehlerhafte Datensätze";
            this.buttonVisible = false;
            document.getElementById("uploadCompleteText").style.display =
              "inline-block";
          }
        } catch (e) {
          this.uploadResultText = "Upload Failed" + "\n" + e.message;
          document.getElementById("uploadCompleteText").style.display =
            "inline-block";
        }

        console.log("Upload process finished");
      }
    },

    stopUpload: async function () {
      this.stopUploadVar = true;
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
    },

    checkPatientIDs: async function (datasets) {
      const patientIDs = new Set();
      const patientBirthdates = new Set();
      const patientNames = new Set();

      try {
        console.log("were here");
        for (const set of datasets) {
          console.log("were here2");
          const dcm = dcmjs.data.DicomMessage.readFile(set, {
            ignoreErrors: true,
          });
          console.log("were here3");
          console.log(dcm);
          try {
            patientIDs.add(dcm.dict["00100020"].Value[0]); // Patient ID
            patientNames.add(dcm.dict["00100010"].Value[0].Alphabetic); // Patient Name
            patientBirthdates.add(dcm.dict["00100030"].Value[0]); // Patient Birthdate
          } catch (e) {
            console.log(e);
          }
        }
        return (
          patientIDs.size <= 1 &&
          patientNames.size <= 1 &&
          patientBirthdates.size <= 1
        );
      } catch (e) {
        //console.log(e);
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
          );

          return response.status;
        } else {
          console.log("Response from server:", text);
        }
      }
    })
    .catch(function (error) {
      //console.log(`Error: ${error.reason_phrase}`);
      return 0;
    });
}
