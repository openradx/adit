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
