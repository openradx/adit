$(function () {
  $("form#dicom_explorer").on("submit", function () {
    $(this)
      .find("input[name]")
      .filter(function () {
        return !this.value || this.name == "query";
      })
      .prop("name", "");
  });
});
