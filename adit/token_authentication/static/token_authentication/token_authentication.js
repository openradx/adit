document.getElementById("generate-token-button").addEventListener("click", generateToken);
window.onload = loadTokenList();

function generateToken() {
    var expiry_time = document.getElementById("select-expiry-time").value;
    var client = document.getElementById("specify-client").value;
    const URL = window.location.href + "/generate_token";
    $.ajax({
        type: "POST",
        url: URL,
        data: {
            "expiry_time": expiry_time,
            "client": client,
            csrfmiddlewaretoken: csrf_token,
        },
        success: generate_token_callback,
    });
};

function generate_token_callback(response) {
    loadTokenList();
}

function deleteToken(token_str) {
    const URL = window.location.href + "/delete_token";
    if (confirm("Are You sure you want to delete the token with ID: " + token_str)) {
        $.ajax({
            type: "POST",
            url: URL,
            data: {
                "token_str": token_str,
                csrfmiddlewaretoken: csrf_token,
            },
            success: delete_token_callback,
        });
    };
};

function delete_token_callback(response) {
    loadTokenList();
    var response_meta = JSON.parse(response)
    if (response_meta["sucess"] == true) {
        //alert(response_meta["message"])
    } else {
        alert(response_meta["message"]);
    };
};

function copyToken(token_str) {
    navigator.clipboard.writeText(token_str);
    //alert("Copied token: " + token_str);
};

function downloadToken(token_str) {
    var token_json = JSON.stringify({
        "Authorization": "Token " + token_str
    });
    var data_json = "data:text/json;charset=utf-8," + encodeURIComponent(token_json);
    var temp_download_node = document.createElement('a');
    temp_download_node.setAttribute("href", data_json);
    temp_download_node.setAttribute("download", "token.json");
    document.body.appendChild(temp_download_node);
    temp_download_node.click();
    temp_download_node.remove();
}

function loadTokenList() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            document.getElementById("token-list-wrapper").innerHTML = this.responseText;
        };
    };
    var URL = window.location + "/_token_list"
    xhttp.open("GET", URL, true);
    xhttp.send();
}