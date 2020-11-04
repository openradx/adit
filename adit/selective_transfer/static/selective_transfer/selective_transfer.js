function selectiveTransferForm() {
    return {
        showHelpMessage: true,
        queryInProgress: false,
        transferInProgress: false,

        init: function (el, refs) {
            this.$form = $(el);
            this.refs = refs;
            this.messageId = 0;
            this.connect();

            const self = this;

            const $advanced_options = this.$form.find("#advanced_options");
            $advanced_options
                .on("hide.bs.collapse", function () {
                    self.updateCookie("hideOptions", true);
                })
                .on("show.bs.collapse", function () {
                    self.updateCookie("hideOptions", false);
                });

            const cookie = JSON.parse(
                Cookies.get("selectiveTransferForm") || "{}"
            );
            if ("hideOptions" in cookie) {
                if (cookie.hideOptions) {
                    $advanced_options.collapse("hide");
                } else {
                    $advanced_options.collapse("show");
                }
            }
            if ("source" in cookie) {
                this.$form.find("[name=source]").val(cookie.source);
            }
            if ("destination" in cookie) {
                this.$form.find("[name=destination]").val(cookie.destination);
            }
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
        updateCookie: function (key, value) {
            const cookie = JSON.parse(
                Cookies.get("selectiveTransferForm") || "{}"
            );
            cookie[key] = value;
            Cookies.set("selectiveTransferForm", JSON.stringify(cookie));
        },
        submitQuery: function () {
            this.showHelpMessage = false;
            this.queryInProgress = true;
            this.$form.find("#error_message").empty();
            this.$form.find("#created_job").empty();
            this.$form.find("#query_results").empty();
            this.submitForm("query");
        },
        submitTransfer: function () {
            this.transferInProgress = true;
            this.submitForm("transfer");
        },
        submitForm(action) {
            const formData = this.$form.serialize();
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

            this.queryInProgress = false;
            this.transferInProgress = false;

            // Replace the HTML as demanded by the server.
            for (const selector in msg) {
                const fromNode = this.$form.find(selector)[0];
                const toNode = fromNode.cloneNode(false);
                toNode.innerHTML = msg[selector];
                morphdom(fromNode, toNode, {
                    onBeforeElUpdated: function (fromEl, toEl) {
                        // We need to preserve the collapse state as it is only
                        // set on the client.
                        if (
                            fromEl.id === "advanced_options" ||
                            fromEl.id === "advanced_options_toggle"
                        ) {
                            for (let i = 0; i < fromEl.attributes.length; i++) {
                                const attr = fromEl.attributes[i];
                                toEl.setAttribute(attr.name, attr.value);
                            }
                        }
                    },
                });
            }
        },
        onServerChanged: function (event) {
            const name = event.target.name;
            const value = event.target.value;
            if (name === "source") {
                this.reset();
            }
            this.updateCookie(name, value);
        },
        reset: function () {
            this.showHelpMessage = true;
            this.$form.find("#error_message").empty();
            this.$form.find("#created_job").empty();
            this.$form.find("#query_results").empty();
        },
    };
}
