// Adapted from https://getbootstrap.com/docs/5.3/customize/color-modes/#javascript
(() => {
  "use strict";

  // Keep in sync with cores/views.py
  const THEME = "theme";

  const getStoredTheme = () =>
    document.documentElement.getAttribute("data-theme-preference");
  const setStoredTheme = (theme) => {
    document.documentElement.setAttribute("data-theme-preference", theme);
    updatePreferences(null, { [THEME]: theme });
  };

  const getPreferredTheme = () => {
    const storedTheme = getStoredTheme();
    if (storedTheme) {
      return storedTheme;
    }

    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  };

  const setTheme = (theme) => {
    if (
      theme === "auto" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
    ) {
      document.documentElement.setAttribute("data-bs-theme", "dark");
    } else {
      document.documentElement.setAttribute("data-bs-theme", theme);
    }
  };

  setTheme(getPreferredTheme());

  const showActiveTheme = (theme, focus = false) => {
    const themeSwitcher = document.querySelector("#theme-switcher");

    if (!themeSwitcher) {
      return;
    }

    // Get the the theme switcher dropdown menu
    const themeMenu = document.querySelector("#theme-switcher > ul");

    // Unselect all theme items in the dropdown menu
    themeMenu.querySelectorAll("[data-bs-theme-value]").forEach((element) => {
      element.classList.remove("active");
      element.setAttribute("aria-pressed", "false");
    });

    // Select the correct theme item in the dropdown menu
    const activeThemeItem = themeMenu.querySelector(
      `[data-bs-theme-value="${theme}"]`
    );
    activeThemeItem.classList.add("active");
    activeThemeItem.setAttribute("aria-pressed", "true");

    // The the href of the current SVG symbol
    const href = activeThemeItem.querySelector("svg use").getAttribute("href");

    // Set the href of the SVG symbol in the theme switcher button
    document
      .querySelector("#theme-switcher > button svg use")
      .setAttribute("href", href);

    if (focus) {
      // @ts-ignore
      themeSwitcher.focus();
    }
  };

  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
      const storedTheme = getStoredTheme();
      if (storedTheme !== "light" && storedTheme !== "dark") {
        setTheme(getPreferredTheme());
      }
    });

  window.addEventListener("DOMContentLoaded", () => {
    showActiveTheme(getPreferredTheme());

    document.querySelectorAll("[data-bs-theme-value]").forEach((toggle) => {
      toggle.addEventListener("click", () => {
        const theme = toggle.getAttribute("data-bs-theme-value");
        setStoredTheme(theme);
        setTheme(theme);
        showActiveTheme(theme, true);
      });
    });
  });
})();
