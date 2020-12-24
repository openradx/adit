$(function () {
    // Enable Bootstrap tooltips everywhere
    $('[data-toggle="tooltip"]').tooltip();
});

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
