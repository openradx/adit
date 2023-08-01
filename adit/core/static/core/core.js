$(function () {
  // Enable Bootstrap tooltips everywhere
  $('[data-bs-toggle="tooltip"]').tooltip();

  // Enable toasts everywhere.
  $(".toast").toast();
});

// A site wide config that is added to the context by adit.core.site.base_context_processor
// and that can be accessed by Javascript
function getAditConfig() {
  return JSON.parse(document.getElementById("adit_config").textContent);
}

// Alpine JS data model connected in _messages_panel.html
// A simple usage example of how to add messages on the client by dispatching
// a custom event can be found in sandbox.html and sandbox.js.
function messages() {
  function capitalize(s) {
    if (typeof s !== "string") return "";
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  return {
    options: {
      nextMessageId: 1,
      duration: 30000,
    },
    messages: [],
    init: function ($el, $watch, $nextTick) {
      this.$el = $el;

      // Auto hide already added messages by the server
      const serverMessages = this.$el.getElementsByClassName("server-message");
      for (let i = 0; i < serverMessages.length; i++) {
        setTimeout(function () {
          serverMessages[i].remove();
        }, this.options.duration);
      }
    },
    /**
     * Add a message to the message list
     * @param {object} message
     * @param {("success"|"warning"|"error")} message.level
     * @param {string} message.title
     * @param {string} message.text
     */
    addMessage: function (message) {
      message.id = this.options.nextMessageId++;
      message.title = capitalize(message.title);
      this.messages.push(message);
      const self = this;
      // Auto hide client message
      setTimeout(function () {
        self.messages.splice(self.messages.indexOf(message), 1);
      }, this.options.duration);
    },
    removeMessage: function (message) {
      this.messages.splice(this.messages.indexOf(message), 1);
    },
  };
}
