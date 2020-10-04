function batchTransferForm() {
    return {
        isDestinationFolder: false,
        nodeTypes: {},
        init() {
            this.nodeTypes = loadData("nodeTypes");
        },
        destinationChanged: function (event) {
            const nodeId = event.currentTarget.value;
            const nodeType = this.nodeTypes[nodeId];
            this.isDestinationFolder = nodeType === "folder";
        },
    };
}
