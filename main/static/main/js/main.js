$(function() {
    window.setTimeout(function() {
        $(".messages-panel-inner .alert").fadeTo(500, 0).slideUp(500, function() {
            $(this).remove(); 
        });
    }, 10000);
});