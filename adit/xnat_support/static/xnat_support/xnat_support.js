// toggle the xnat options div
$(document).ready(toggle_fields("False"));

function toggle() {
    const ae_title = document.getElementById('id_source').value;
    const URL = window.location.origin + "/xnat-support" + "/check-xnat-src/" + ae_title;
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
    document.getElementById('id_source').onchange = toggle;
};

// find projects button
document.getElementById("btn-find-projects").addEventListener("click", find_projects);

function find_projects() {
    const ae_title = document.getElementById('id_source').value;
    const URL = window.location.origin + "/xnat-support" + "/find-xnat-projects/" + ae_title;
    $.ajax({
        type: "GET",
        url: URL,
        success: list_projects,
    });
}

function list_projects(response) {
    document.getElementById("project-id-list").innerHTML += "<ul class='list-group'>";
    for (var project_id of response) {
        document.getElementById("project-id-list").innerHTML += "<li class='list-group-item'>" + project_id + "</li>"
    };
    document.getElementById("project-id-list").innerHTML += "</ul>"
}