// toggle the xnat options div
const SOURCE_OPTIONS_ID = document.currentScript.getAttribute("SOURCE_OPTIONS_ID");
const SOURCE_SELECT_ID = document.currentScript.getAttribute("SOURCE_SELECT_ID");
const DEST_OPTIONS_ID = document.currentScript.getAttribute("DEST_OPTIONS_ID");
const DEST_SELECT_ID = document.currentScript.getAttribute("DEST_SELECT_ID");

function toggle(area_css_id, server) {
    const ae_title = document.getElementById(server).value;
    const URL = window.location.origin + "/xnat-support" + "/check-xnat-src/" + ae_title;
    $.ajax({
        type: "GET",
        url: URL,
        success: function(res) {
            toggle_fields(res, area_css_id);
        },
    });
};

function toggle_fields(response, area_css_id) {
    if (response == "False") {
        document.getElementById(area_css_id).style.display = 'none';
    } else {
        document.getElementById(area_css_id).style.display = '';
    };
};

window.onload = function () {
    if (SOURCE_OPTIONS_ID != null && SOURCE_SELECT_ID != null) {
        toggle(SOURCE_OPTIONS_ID, SOURCE_SELECT_ID);
        document.getElementById(SOURCE_SELECT_ID).onchange = function(){
            toggle(SOURCE_OPTIONS_ID, SOURCE_SELECT_ID);
        };
    };
    if (DEST_OPTIONS_ID != null && DEST_SELECT_ID != null) {
        toggle(DEST_OPTIONS_ID, DEST_SELECT_ID);
        document.getElementById(DEST_SELECT_ID).onchange = function(){
            toggle(DEST_OPTIONS_ID, DEST_SELECT_ID);
        };
    };
};

try {
    var target = document.querySelector("#query_results");
    var observer = new MutationObserver(function() {
        toggle(SOURCE_OPTIONS_ID, SOURCE_SELECT_ID);
        toggle(DEST_OPTIONS_ID, DEST_SELECT_ID);
    });
    var config = { attributes: true, childList: true, characterData: true }
    observer.observe(target, config);
} catch (error) {};


// find projects button
try {
    const SOURCE_BTN_ID = "btn-"+SOURCE_OPTIONS_ID+"-find-projects"
    document.getElementById(SOURCE_BTN_ID).addEventListener("click", function() {
        find_projects(SOURCE_SELECT_ID, SOURCE_OPTIONS_ID)
    });
} catch (error) {};
try {
    const DEST_BTN_ID = "btn-"+DEST_OPTIONS_ID+"-find-projects"
    document.getElementById(DEST_BTN_ID).addEventListener("click", function() {
        find_projects(DEST_SELECT_ID, DEST_OPTIONS_ID)
    });
} catch (error) {};

function find_projects(server, options_id) {
    const ae_title = document.getElementById(server).value;
    const URL = window.location.origin + "/xnat-support" + "/find-xnat-projects/" + ae_title;
    document.getElementById(options_id+"project-id-list").innerHTML = "";
    $.ajax({
        type: "GET",
        url: URL,
        success: function(res) {
            list_projects(res, options_id)
        },
    });
};

function list_projects(response, options_id) {
    for (var xnat_project_id of response) {
        document.getElementById(options_id+"project-id-list").innerHTML += "<li class='list-group-item user-select-all' style='padding:0px; border: 0px solid #ced4da; margin-bottom: 2px;'><a>" + xnat_project_id + "</a></li>"
    };
}