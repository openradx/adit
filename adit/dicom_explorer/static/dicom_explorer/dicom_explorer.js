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

$(document).ready(toggle());

function toggle() {
    const ae_title = document.getElementById('id_server').value;
    const URL = window.location.origin + "/xnat-support" + "/check-xnat/" + ae_title;
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
        document.getElementById('div_id_project_id').style.display = 'none';
    } else {
        document.getElementById('div_id_project_id').style.display = '';
    };
}

window.onload = function () {
    document.getElementById('id_server').onchange = toggle;
};