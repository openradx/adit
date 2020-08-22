function loadData(jsonElementId) {
    return JSON.parse(document.getElementById(jsonElementId).textContent);
}

// From https://stackoverflow.com/a/2117523/166229
function uuidv4() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (
        c
    ) {
        var r = (Math.random() * 16) | 0,
            v = c == "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
    });
}

function alertMessages() {
    return {
        options: {
            nextMessageId: 1,
            duration: 10000,
        },
        messages: [],
        autoHideServerMessages: function (panel) {
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
        addMessage: function (message) {
            message.id = this.options.nextMessageId;
            this.messages.push(message);
            const self = this;
            setTimeout(function () {
                self.messages.splice(self.messages.indexOf(message), 1);
            }, this.options.duration);
        },
    };
}
