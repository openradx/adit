function selectiveTransferForm() {
    return {
        init: function (el) {
            this.$el = $(el);
            this.messageId = 0;
            this.connect();
        },
        connect: function () {
            const self = this;

            const wsScheme =
                window.location.protocol == "https:" ? "wss" : "ws";
            const wsUrl =
                wsScheme +
                "://" +
                window.location.host +
                "/ws/selective-transfer";

            const ws = new WebSocket(wsUrl);
            ws.onopen = function () {
                console.info("Socket open.");
            };
            ws.onclose = function (event) {
                console.info(
                    "Socket closed. Reconnect will be attempted in 1 second.",
                    event.reason
                );
                setTimeout(function () {
                    self.connect(wsUrl);
                }, 1000);
            };
            ws.onmessage = function (event) {
                const msg = JSON.parse(event.data);
                self.handleMessage(msg);
            };
            ws.onerror = function (err) {
                console.error(
                    "Socket encountered error: ",
                    err.message,
                    "Closing socket"
                );
                ws.close();
            };
            this.ws = ws;
        },
        submitQuery: function () {
            this.submitForm("query");
        },
        submitTransfer: function () {
            this.submitForm("transfer");
        },
        submitForm(action) {
            const formData = this.$el.serialize();
            this.ws.send(
                JSON.stringify({
                    messageId: ++this.messageId,
                    action: action,
                    data: formData,
                })
            );
        },
        handleMessage: function (msg) {
            console.debug("Received message:", msg);
            const messageId = msg.messageId;
            delete msg.messageId;
            if (messageId !== this.messageId) {
                console.debug("Discarding message with ID: " + messageId);
                return;
            }

            // Replace the HTML as demanded by the server.
            for (const elementId in msg) {
                const fromNode = this.$el.find("#" + elementId)[0];
                const toNode = fromNode.cloneNode(false);
                toNode.innerHTML = msg[elementId];
                morphdom(fromNode, toNode);
            }
        },
        updateCookie: function () {},
        reset: function () {},
    };
}
