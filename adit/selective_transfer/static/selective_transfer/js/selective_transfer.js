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
        advancedOptionsVisible: false,
        noSearchYet: true,
        noResults: false,
        errorMessage: "",
        successJobId: null,
        searchInProgress: false,
        selectAllChecked: false,
        init: function ($refs) {
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
                console.log("Socket open.");
            };
            ws.onclose = function (e) {
                console.log(
                    "Socket closed. Reconnect will be attempted in 1 second.",
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
        },
        initAdvancedOptions: function () {
            const self = this;
            $(this.$refs.advancedOptions)
                .on("show.bs.collapse", function () {
                    self.advancedOptionsVisible = true;
                    self.updateCookie();
                })
                .on("hide.bs.collapse", function () {
                    self.advancedOptionsVisible = false;
                    self.updateCookie();
                });
        },
        loadCookie: function () {
            const data = Cookies.getJSON("selectiveTransferForm");
            if (data) {
                this.formData.source = data.source;
                this.formData.destination = data.destination;
            }

            if (data && data.advancedOptionsVisible) {
                $(this.$refs.advancedOptions).collapse("show");
            } else {
                $(this.$refs.advancedOptions).collapse("hide");
            }
        },
        updateCookie: function () {
            Cookies.set("selectiveTransferForm", {
                source: this.formData.source,
                destination: this.formData.destination,
                advancedOptionsVisible: this.advancedOptionsVisible,
            });
        },
        reset: function (noSearchYet) {
            this.noSearchYet = !!noSearchYet;
            this.selectAllChecked = false;
            this.queryResults = [];
            this.noResults = false;
            this.errorMessage = "";
            this.successJobId = null;
            this.searchInProgress = false;
        },
        submitQuery: function () {
            this.reset();
            this.searchInProgress = true;
            this.currentQueryId = uuidv4();

            const data = {
                action: "query_studies",
                queryId: this.currentQueryId,
                query: this.formData,
            };

            console.debug("Submitting query:", data);

            this.ws.send(JSON.stringify(data));
        },
        handleMessage: function (data) {
            console.debug("Received message:", data);
            this.searchInProgress = false;
            if (data.status === "error") {
                this.errorMessage = data.message;
            } else if (data.status === "success") {
                const queryId = data.queryId;
                if (this.currentQueryId === queryId) {
                    this.queryResults = data.queryResults;
                    if (this.queryResults.length === 0) {
                        this.noResults = true;
                    }
                    this.currentQueryId = null;
                }
            }
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

            this.errorMessage = "";

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

            console.debug("Submitting transfer:", data);

            $.ajax({
                url: "/selective-transfer/create/",
                method: "POST",
                headers: { "X-CSRFToken": csrftoken },
                dataType: "json",
                contentType: "application/json",
                data: JSON.stringify(data),
            })
                .done(function (data) {
                    console.info(data);
                    self.reset();
                    self.successJobId = data.id;
                })
                .fail(function (jqXHR) {
                    console.error(jqXHR);
                    let errorString = "";
                    const errorMessages = jqXHR.responseJSON;
                    if (jqXHR.status === 400) {
                        for (const field in errorMessages) {
                            errorString += capitalize(field);
                            errorString += ": " + errorMessages[field];
                            errorString += "\n";
                        }
                    }
                    self.errorMessage = errorString;
                });
        },
    };
}
