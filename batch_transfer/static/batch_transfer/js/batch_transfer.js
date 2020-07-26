$(function() {
    if ($('body#batch_transfer_job_create')) {
        const archivePasswordField = $('div#div_id_archive_password');
        function showHideArchivePasswordField(nodeType) {
            if (nodeType === 'folder') {
                archivePasswordField.show();
            } else {
                archivePasswordField.hide();
            }
        }

        const nodeId = $('select#id_destination').val();
        const nodeType = nodeTypes[nodeId];
        showHideArchivePasswordField(nodeType);

        $('select#id_destination').on('change', function(e) {
            const nodeId = e.currentTarget.value;
            const nodeType = nodeTypes[nodeId];
            showHideArchivePasswordField(nodeType);
        });
    }
});