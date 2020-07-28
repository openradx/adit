$.adit = {
    // See https://docs.djangoproject.com/en/3.0/ref/templates/builtins/#json-script
    loadData: function(jsonElementId) {
        return JSON.parse(document.getElementById(jsonElementId).textContent);
    }
}

$(function() {
    window.setTimeout(function() {
        $(".messages-panel-inner .alert").fadeTo(500, 0).slideUp(500, function() {
            $(this).remove(); 
        });
    }, 10000);
});