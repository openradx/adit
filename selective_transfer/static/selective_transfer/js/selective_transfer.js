function selectiveTransferForm() {
    return {
        formData: {
            source: "",
            destination: "",
            patient_id: "",
            patient_name: "",
            patient_birth_date: "",
            study_date: "",
            modality: "",
            accession_number: "",
            pseudonym: "",
            archive_password: "",
            trial_protocol_id: "",
            trial_protocol_name: "",
        },
        queryResults: [],
        currentQueryId: null,
        advancedOptionsCollapsed: true,
        noSearchYet: true,
        searchInProgress: false,
        selectAllChecked: false,
        init: function ($dispatch, $refs) {
            this.$dispatch = $dispatch;
            this.$refs = $refs;

            this.connect();
            this.initAdvancedOptions();
            this.loadCookie();
        },
        connect: function () {
            const self = this;

            const wsScheme =
                window.location.protocol == "https:" ? "wss" : "ws";
            const wsUrl =
                wsScheme +
                "://" +
                window.location.host +
                "/ws/selective-transfer";

            const ws = new WebSocket(wsUrl);
            ws.onopen = function () {
                console.log("Socket is opened.");
            };
            ws.onclose = function (e) {
                console.log(
                    "Socket is closed. Reconnect will be attempted in 1 second.",
                    e.reason
                );
                setTimeout(function () {
                    self.connect(wsUrl);
                }, 1000);
            };
            ws.onmessage = function (e) {
                const data = JSON.parse(e.data);
                self.handleMessage(data);
            };
            ws.onerror = function (err) {
                console.error(
                    "Socket encountered error: ",
                    err.message,
                    "Closing socket"
                );
                ws.close();
            };
            this.ws = ws;

            // FIXME for debugging
            // this.currentQueryId = foobar.queryId;
            // this.handleMessage(foobar);
        },
        initAdvancedOptions: function () {
            const self = this;
            $(this.$refs.advancedOptions)
                .on("show.bs.collapse", function () {
                    self.advancedOptionsCollapsed = false;
                    self.updateCookie();
                })
                .on("hide.bs.collapse", function () {
                    self.advancedOptionsCollapsed = true;
                    self.updateCookie();
                });
        },
        loadCookie: function () {
            const data = Cookies.getJSON("selectiveTransferForm");
            if (data) {
                this.formData.source = data.source;
                this.formData.destination = data.destination;
            }

            if (data.advancedOptionsCollapsed) {
                $(this.$refs.advancedOptions).collapse("hide");
            } else {
                $(this.$refs.advancedOptions).collapse("show");
            }
        },
        updateCookie: function () {
            Cookies.set("selectiveTransferForm", {
                source: this.formData.source,
                destination: this.formData.destination,
                advancedOptionsCollapsed: this.advancedOptionsCollapsed,
            });
        },
        handleMessage: function (data) {
            console.log(data);
            if (data.status === "ERROR") {
                this.showError(data.message);
            } else if (data.status === "SUCCESS") {
                const queryId = data.queryId;
                if (this.currentQueryId === queryId) {
                    this.searchInProgress = false;
                    this.queryResults = data.queryResults;
                    this.currentQueryId = null;
                }
            }
        },
        submitQuery: function () {
            this.queryResults = [];
            this.noSearchYet = false;
            this.searchInProgress = true;
            this.currentQueryId = uuidv4();
            this.ws.send(
                JSON.stringify({
                    action: "query_studies",
                    queryId: this.currentQueryId,
                    query: this.formData,
                })
            );
        },
        watchSelectAll: function (event) {
            const selectAll = event.target.checked;
            if (selectAll) {
                for (result of this.queryResults) {
                    result.selected = true;
                }
            } else {
                for (result of this.queryResults) {
                    delete result.selected;
                }
            }
            this.selectionChanged();
        },
        selectionChanged: function () {
            let allSelected = true;
            for (result of this.queryResults) {
                if (!result.selected) {
                    allSelected = false;
                    break;
                }
            }
            this.selectAllChecked = allSelected;
        },
        submitTransfer: function () {
            const self = this;

            const patientIds = [];
            const studiesToTransfer = this.queryResults
                .filter(function (study) {
                    return !!study.selected;
                })
                .map(function (study) {
                    if (patientIds.indexOf(study.PatientID) === -1) {
                        patientIds.push(study.PatientID);
                    }

                    return {
                        patient_id: study.PatientID,
                        study_uid: study.StudyInstanceUID,
                        pseudonym: self.formData.pseudonym,
                    };
                });

            if (this.formData.pseudonym && patientIds.length > 1) {
                this.showError(
                    "When a pseudonym is provided only studies of one patient can be transferred."
                );
            } else if (!this.formData.source) {
                this.showError("You must select a source.");
            } else if (!this.formData.destination) {
                this.showError("You must select a destination.");
            } else if (studiesToTransfer.length === 0) {
                this.showError("You must at least select one study.");
            } else {
                const csrftoken = document.querySelector(
                    "[name=csrfmiddlewaretoken]"
                ).value;

                const data = {
                    source: this.formData.source,
                    destination: this.formData.destination,
                    archive_password: this.formData.archive_password,
                    trial_protocol_id: this.formData.trial_protocol_id,
                    trial_protocol_name: this.formData.trial_protocol_name,
                    tasks: studiesToTransfer,
                };

                $.ajax({
                    url: "/selective-transfer/create/",
                    method: "POST",
                    headers: { "X-CSRFToken": csrftoken },
                    dataType: "json",
                    contentType: "application/json",
                    data: JSON.stringify(data),
                })
                    .done(function (data) {
                        self.showSuccess(
                            "Successfully submitted transfer job with ID " +
                                data.id
                        );
                    })
                    .fail(function (response) {
                        console.error(response);
                    });
            }
        },
        showSuccess: function (text) {
            this.$dispatch("main:add-message", {
                type: "alert-success",
                text: text,
            });
        },
        showError: function (text) {
            this.$dispatch("main:add-message", {
                type: "alert-danger",
                text: text,
            });
        },
    };
}

// TODO Remove!
const foobar = {
    status: "SUCCESS",
    queryId: "dc9e071b-d8db-4b57-824b-76bad3f8c96c",
    queryResults: [
        {
            SpecificCharacterSet: "ISO_IR 100",
            StudyDate: "20190915",
            StudyTime: "183223.0",
            AccessionNumber: "0062094332",
            QueryRetrieveLevel: "STUDY",
            StudyDescription: "MRT-Kopf",
            PatientName: "Banana^Ben",
            PatientID: "10002",
            PatientBirthDate: "19620218",
            StudyInstanceUID:
                "1.2.840.113845.11.1000000001951524609.20200705182751.2689480",
            Modalities: ["MR"],
        },
        {
            SpecificCharacterSet: "ISO_IR 100",
            StudyDate: "20180327",
            StudyTime: "180756.0",
            AccessionNumber: "0062115923",
            QueryRetrieveLevel: "STUDY",
            StudyDescription: "CT des Schädels",
            PatientName: "Banana^Ben",
            PatientID: "10002",
            PatientBirthDate: "19620218",
            StudyInstanceUID:
                "1.2.840.113845.11.1000000001951524609.20200705180932.2689477",
            Modalities: ["CT"],
        },
        {
            SpecificCharacterSet: "ISO_IR 100",
            StudyDate: "20180913",
            StudyTime: "185458.0",
            AccessionNumber: "0062115944",
            QueryRetrieveLevel: "STUDY",
            StudyDescription: "CT des Schädels",
            PatientName: "Banana^Ben",
            PatientID: "10002",
            PatientBirthDate: "19620218",
            StudyInstanceUID:
                "1.2.840.113845.11.1000000001951524609.20200705185333.2689485",
            Modalities: ["CT"],
        },
    ],
};
