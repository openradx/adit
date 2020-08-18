function alertMessages() {
    return {
        options: {
            nextMessageId: 1,
            duration: 3000,
        },
        messages: [],
        autoHideServerMessages(panel) {
            const serverMessages = panel.getElementsByClassName(
                "server-message"
            );
            for (const msg of serverMessages) {
                setTimeout(
                    function () {
                        msg.remove();
                    }.this.options.duration
                );
            }
        },
        addMessage(message) {
            message.id = this.options.nextMessageId;
            this.messages.push(message);
            const self = this;
            setTimeout(function () {
                self.messages.splice(self.messages.indexOf(message), 1);
            }, this.options.duration);
        },
    };
}

function loadData(jsonElementId) {
    return JSON.parse(document.getElementById(jsonElementId).textContent);
}
