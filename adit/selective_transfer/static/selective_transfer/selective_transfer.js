function selectiveTransferForm() {
  const config = getAditConfig();
  const storageKey = "selectiveTransferForm-" + config.user_id;

  return {
    showHelpMessage: true,
    queryInProgress: false,
    transferInProgress: false,
    isDestinationFolder: false,

    init: function (el, refs) {
      this.$form = $(el);
      this.refs = refs;
      this.connect();

      const self = this;

      const $advancedOptions = this.$form.find("#advanced_options");
      $advancedOptions
        .on("hide.bs.collapse", function () {
          self.updateStorage("hideOptions", true);
        })
        .on("show.bs.collapse", function () {
          self.updateStorage("hideOptions", false);
        });

      this.restoreFromStorage($advancedOptions);
    },
    connect: function () {
      const self = this;

      const wsScheme = window.location.protocol == "https:" ? "wss" : "ws";
      const wsUrl =
        wsScheme + "://" + window.location.host + "/ws/selective-transfer";

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
    setSelectOption: function (select, value) {
      const options = select.options;
      let valueToSet = "";
      for (let i = 0, len = options.length; i < len; i++) {
        if (i == 0) valueToSet = options[i].value;
        if (options[i].value === value) valueToSet = value;
      }
      select.value = valueToSet;
    },
    loadFromStorage: function () {
      let item;
      try {
        item = JSON.parse(window.localStorage.getItem(storageKey) || "{}");
        if (typeof item !== "object") {
          item = {};
        }
      } catch {
        item = {};
      }
      return item;
    },
    updateStorage: function (key, value) {
      const item = this.loadFromStorage();
      item[key] = value;
      window.localStorage.setItem(storageKey, JSON.stringify(item));
    },
    restoreFromStorage: function ($advancedOptions) {
      const item = this.loadFromStorage();

      if ("hideOptions" in item) {
        if (item.hideOptions) {
          $advancedOptions.collapse("hide");
        } else {
          $advancedOptions.collapse("show");
        }
      }

      if ("source" in item) {
        const source = this.$form.find("[name=source]")[0];
        this.setSelectOption(source, item.source);
      }

      if ("destination" in item) {
        const destination = this.$form.find("[name=destination]")[0];
        this.setSelectOption(destination, item.destination);
        this.onDestinationChanged(destination);
      }

      if ("urgent" in item) {
        const urgentEl = this.$form.find("[name=urgent]")[0];
        if (urgentEl) {
          urgentEl.checked = item.urgent;
        }
      }
    },
    submitQuery: function () {
      this.showHelpMessage = false;
      this.queryInProgress = true;
      this.$form.find("#error_message").empty();
      this.$form.find("#created_job").empty();
      this.$form.find("#query_results").empty();
      this.submitForm("query");
    },
    cancelQuery: function () {
      this.ws.send(
        JSON.stringify({
          action: "cancelQuery",
        })
      );
      this.queryInProgress = false;
      this.showHelpMessage = true;
    },
    submitTransfer: function () {
      this.transferInProgress = true;
      this.submitForm("transfer");
    },
    submitForm(action) {
      const formData = this.$form.serialize();
      this.ws.send(
        JSON.stringify({
          action: action,
          data: formData,
        })
      );
    },
    handleMessage: function (msg) {
      //console.debug("Received message:", msg);

      this.queryInProgress = false;
      this.transferInProgress = false;
      this.showHelpMessage = false;

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
      const name = event.currentTarget.name;
      const value = event.currentTarget.value;
      this.updateStorage(name, value);

      if (name === "destination") {
        this.onDestinationChanged(event.currentTarget);
      }

      if (name === "source") {
        this.reset();
      }
    },
    onDestinationChanged(selectEl) {
      const option = selectEl.options[selectEl.selectedIndex];
      this.isDestinationFolder = option.dataset.node_type === "folder";
    },
    onUrgencyChanged: function (event) {
      const name = event.currentTarget.name;
      const value = event.currentTarget.checked;
      this.updateStorage(name, value);
    },
    reset: function () {
      this.showHelpMessage = true;
      this.$form.find("#error_message").empty();
      this.$form.find("#created_job").empty();
      this.$form.find("#query_results").empty();
    },
  };
}
