$(function () {
    let ws = null;

    function connect(url) {
        ws = new WebSocket(url);
        ws.onopen = function () { };
        ws.onmessage = function (e) {
            const data = JSON.parse(e.data);
            console.log(data);
        };
        ws.onclose = function (e) {
            console.log(
                "Socket is closed. Reconnect will be attempted in 1 second.",
                e.reason
            );
            setTimeout(function () {
                connect(url);
            }, 1000);
        };
        ws.onerror = function (err) {
            console.error(
                "Socket encountered error: ",
                err.message,
                "Closing socket"
            );
            ws.close();
        };
    }

    function getQueryParams() {
        const form = $("form#study_query_form");
        return {
            source: form.find('select[name="source"]').val(),
            patient_id: form.find('input[name="patient_id"]').val(),
            patient_name: form.find('input[name="patient_name"]').val(),
            patient_birth_date: form
                .find('input[name="patient_birth_date"]')
                .val(),
            study_date: form.find('input[name="study_date"]').val(),
            modality: form.find('input[name="modality"]').val(),
            accession_number: form.find('input[name="accession_number"]').val(),
        };
    }

    var wsScheme = window.location.protocol == "https:" ? "wss" : "ws";
    var wsUrl = wsScheme + "://" + window.location.host + "/ws/selective-transfer";

    connect(wsUrl);

    $(".query_field").keyup(function (event) {
        if (event.keyCode === 13) {
            const queryParams = getQueryParams();
            ws.send(JSON.stringify({
                action: "query_studies",
                query: queryParams
            }));
        }
    });
});
