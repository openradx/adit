function selectiveTransferForm() {
  const config = getAditConfig();
  const STORAGE_KEY = "selectiveTransferForm-" + config.user_id;
  const SOURCE_KEY = "source";
  const DESTINATION_KEY = "destination";
  const ADVANCED_OPTIONS_COLLAPSED_KEY = "advancedOptionsCollapsed";
  const URGENT_KEY = "urgent";

  function loadState() {
    let state = {};
    try {
      state = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
      if (typeof state !== "object") state = {};
    } catch (error) {
      console.error(`Invalid state from local storage: ${error}`);
    }
    return state;
  }

  function updateState(key, value) {
    const state = loadState();
    state[key] = value;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  return {
    isDestinationFolder: false,

    init: function (formEl) {
      this.formEl = formEl;

      const advancedOptionsEl = this.formEl.querySelector("#advanced_options");
      advancedOptionsEl.addEventListener("hide.bs.collapse", function () {
        updateState(ADVANCED_OPTIONS_COLLAPSED_KEY, true);
      });
      advancedOptionsEl.addEventListener("show.bs.collapse", function () {
        updateState(ADVANCED_OPTIONS_COLLAPSED_KEY, false);
      });

      this._restoreState();
    },
    _restoreState: function () {
      const state = loadState();

      if (ADVANCED_OPTIONS_COLLAPSED_KEY in state) {
        const advancedOptionsEl =
          this.formEl.querySelector("#advanced_options");
        if (state[ADVANCED_OPTIONS_COLLAPSED_KEY])
          advancedOptionsEl.collapse("hide");
        else advancedOptionsEl.collapse("show");
      }

      function setSelectedOption(selectEl, value) {
        const optionEls = selectEl.options;
        let valueToSet = "";
        for (let i = 0, len = optionEls.length; i < len; i++) {
          if (i == 0) valueToSet = optionEls[i].value;
          if (optionEls[i].value === value) valueToSet = value;
        }
        selectEl.value = valueToSet;
      }

      if (SOURCE_KEY in state) {
        const sourceEl = this.formEl.querySelector("[name=source]");
        setSelectedOption(sourceEl, state[SOURCE_KEY]);
      }

      if (DESTINATION_KEY in state) {
        const destinationEl = this.formEl.querySelector("[name=destination]");
        setSelectedOption(destinationEl, state[DESTINATION_KEY]);
        this._checkDestination(destinationEl);
      }

      if (URGENT_KEY in state) {
        const urgentEl = this.formEl.querySelector("[name=urgent]");
        if (urgentEl) urgentEl.checked = state[URGENT_KEY];
      }
    },
    _reset: function () {
      const buttonEl = this.formEl.querySelector("[value=reset]");
      buttonEl.click();
    },
    onDicomNodeChanged: function (event) {
      const name = event.currentTarget.name;
      const value = event.currentTarget.value;
      updateState(name, value);

      if (name === "source") this._reset();
      if (name === "destination") this._checkDestination(event.currentTarget);
    },
    _checkDestination(selectEl) {
      const option = selectEl.options[selectEl.selectedIndex];
      this.isDestinationFolder = option.dataset.node_type === "folder";
    },
    onUrgencyChanged: function (event) {
      const name = event.currentTarget.name;
      const value = event.currentTarget.checked;
      updateState(name, value);
    },
    onStartTransfer: function (event) {
      const formEl = this.formEl;
      const buttonEl = event.currentTarget;
      buttonEl.style.pointerEvents = "none";

      function disableTransferButton() {
        // We can only disable the button after the message was send as otherwise
        // htmx won't send the message.
        buttonEl.disabled = true;
        formEl.removeEventListener("htmx:wsAfterSend", disableTransferButton);
      }
      formEl.addEventListener("htmx:wsAfterSend", disableTransferButton);
    },
  };
}
