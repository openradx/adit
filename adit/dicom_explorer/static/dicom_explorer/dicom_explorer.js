$(document).ready(function () {
    $("form#dicom_explorer").submit(function () {
        $(this)
            .find("input[name]")
            .filter(function () {
                return !this.value || this.name == "query";
            })
            .prop("name", "");
    });
});

$(document).ready(toggle_fields("False"));

function toggle() {
    const ae_title = document.getElementById('id_server').value;
    const URL = window.location.origin + "/xnat-support" + "/check-xnat-src/" + ae_title;
    console.log(URL)
    $.ajax({
        type: "GET",
        url: URL,
        success: toggle_fields,
    });
};

function toggle_fields(response) {
    console.log();
    if (response == "False") {
        document.getElementById('xnat-options').style.display = 'none';
    } else {
        document.getElementById('xnat-options').style.display = '';
    };
}

window.onload = function () {
    document.getElementById('id_server').onchange = toggle;
};