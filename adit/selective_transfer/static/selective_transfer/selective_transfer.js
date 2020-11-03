function selectiveTransferForm() {
    return {
        initialHelpMessage: true,
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
            this.initialHelpMessage = false;
            this.submitForm("query");
        },
        submitTransfer: function () {
            this.initialHelpMessage = false;
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

            // Save focus and possible caret position.
            const prevActiveElement = document.activeElement;
            const prevSelectionStart =
                prevActiveElement && prevActiveElement.selectionStart;
            const prevSelectionEnd =
                prevActiveElement && prevActiveElement.selectionEnd;

            // Replace the HTML as demanded by the server.
            for (const elementId in msg) {
                const $el = this.$el.find("#" + elementId);
                $el.html(msg[elementId]);
            }

            // Restore focus and caret position after element was replaced.
            const activeElement = document.activeElement;
            if (activeElement && activeElement !== prevActiveElement) {
                const name = prevActiveElement.name;
                if (name) {
                    const $el = this.$el.find("[name=" + name + "]");
                    $el.focus();
                    const el = $el[0];
                    if (el && el.type === "text") {
                        el.setSelectionRange(
                            prevSelectionStart,
                            prevSelectionEnd
                        );
                    }
                }
            }
        },
        updateCookie: function () {},
        reset: function () {},
    };
}
