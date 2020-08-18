function queryForm() {
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
        },
        ws: null,
        getUrl() {
            var wsScheme = window.location.protocol == "https:" ? "wss" : "ws";
            return (
                wsScheme +
                "://" +
                window.location.host +
                "/ws/selective-transfer"
            );
        },
        connect() {
            const url = this.getUrl();
            this.ws = new WebSocket(url);
            this.ws.onopen = function () {};
            this.ws.onmessage = function (e) {
                const data = JSON.parse(e.data);
                console.log(data);
            };
            this.ws.onclose = function (e) {
                console.log(
                    "Socket is closed. Reconnect will be attempted in 1 second.",
                    e.reason
                );
                setTimeout(function () {
                    this.connect(url);
                }, 1000);
            };
            this.ws.onerror = function (err) {
                console.error(
                    "Socket encountered error: ",
                    err.message,
                    "Closing socket"
                );
                this.ws.close();
            };
        },
        submitData(event, dispatch) {
            if (event.keyCode == 13) {
                console.log("here");
                console.log(dispatch);
                window.dispatch = dispatch;
                dispatch("main:add-message", {
                    type: "alert-danger",
                    text: "foobar",
                });
                // this.ws.send(
                //     JSON.stringify({
                //         action: "query_studies",
                //         query: this.formData,
                //     })
                // );
            }
        },
    };
}
