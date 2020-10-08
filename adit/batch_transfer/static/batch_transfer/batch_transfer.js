function batchTransferForm() {
    return {
        isDestinationFolder: false,
        destinationChanged: function (event) {
            const select = event.currentTarget;
            const option = select.options[select.selectedIndex];
            this.isDestinationFolder = option.dataset.node_type === "folder";
        },
    };
}
