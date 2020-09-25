$(function () {
    new ClipboardJS(".clipboard");
});

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

function capitalize(s) {
    if (typeof s !== "string") return "";
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function messages() {
    return {
        options: {
            nextMessageId: 1,
            duration: 10000,
        },
        messages: [],
        init: function ($el, $watch, $nextTick) {
            this.$el = $el;

            // Auto hide server messages
            const serverMessages = this.$el.getElementsByClassName(
                "server-message"
            );
            for (let i = 0; i < serverMessages.length; i++) {
                setTimeout(function () {
                    serverMessages[i].remove();
                }, this.options.duration);
            }
        },
        addMessage: function (message) {
            message.id = this.options.nextMessageId++;
            message.title = capitalize(message.level);
            this.messages.push(message);
            const self = this;
            setTimeout(function () {
                //self.messages.splice(self.messages.indexOf(message), 1);
            }, this.options.duration);
        },
        removeMessage: function (message) {
            this.messages.splice(this.messages.indexOf(message), 1);
        },
    };
}
