/**
 * Slideshow functionality for ADIT landing page
 * Handles automatic cycling and manual navigation of screenshot slides
 * Includes proper cleanup for SPA-style navigation (MkDocs Material instant loading)
 */

// Constants
const SLIDE_INTERVAL_MS = 4000;

let slideIndex = 0;
let timer = null;
let eventListeners = [];
let mutationObserver = null;

/**
 * Update screen reader announcement for current slide
 * @param {number} current - Current slide number (0-indexed)
 * @param {number} total - Total number of slides
 */
function announceSlide(current, total) {
  const statusElement = document.getElementById("slideshow-status");
  if (statusElement) {
    statusElement.textContent = `Slide ${current + 1} of ${total}`;
  }
}

/**
 * Display a specific slide and update navigation dots
 * @param {number} index - The index of the slide to display
 */
function showSlide(index) {
  const slidesWrapper = document.querySelector(".slides-wrapper");
  const dots = document.querySelectorAll(".dot");

  // Guard: Exit early if slideshow markup is not present on this page
  if (!slidesWrapper || dots.length === 0) {
    cleanupSlideshow();
    return;
  }

  const totalSlides = dots.length;

  if (index >= totalSlides) slideIndex = 0;
  if (index < 0) slideIndex = totalSlides - 1;

  slidesWrapper.style.transform = `translateX(-${slideIndex * 100}%)`;

  dots.forEach((dot, i) => {
    dot.classList.remove("active");
    dot.setAttribute("aria-pressed", "false");
    dot.setAttribute("aria-selected", "false");
  });
  dots[slideIndex].classList.add("active");
  dots[slideIndex].setAttribute("aria-pressed", "true");
  dots[slideIndex].setAttribute("aria-selected", "true");

  // Announce slide change to screen readers
  announceSlide(slideIndex, totalSlides);

  clearTimeout(timer);
  timer = setTimeout(() => {
    slideIndex++;
    showSlide(slideIndex);
  }, SLIDE_INTERVAL_MS);
}

/**
 * Navigate to the next or previous slide
 * @param {number} n - Direction to move (-1 for previous, 1 for next)
 */
function changeSlide(n) {
  slideIndex += n;
  showSlide(slideIndex);
}

/**
 * Navigate to a specific slide
 * @param {number} n - The index of the slide to display
 */
function currentSlide(n) {
  slideIndex = n;
  showSlide(slideIndex);
}

/**
 * Clean up timer and event listeners to prevent memory leaks
 * This is critical for SPA-style navigation where beforeunload doesn't fire
 */
function cleanupSlideshow() {
  // Clear the timer
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }

  // Remove all tracked event listeners
  eventListeners.forEach(({ element, event, handler }) => {
    element.removeEventListener(event, handler);
  });
  eventListeners = [];

  // Disconnect mutation observer
  if (mutationObserver) {
    mutationObserver.disconnect();
    mutationObserver = null;
  }
}

/**
 * Add an event listener and track it for cleanup
 * @param {Element} element - The element to attach the listener to
 * @param {string} event - The event type
 * @param {Function} handler - The event handler function
 */
function addTrackedEventListener(element, event, handler) {
  element.addEventListener(event, handler);
  eventListeners.push({ element, event, handler });
}

// Initialize slideshow when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  // Guard: Only initialize if slideshow markup exists on this page
  const slideshowContainer = document.querySelector(".slideshow-container");
  const slidesWrapper = document.querySelector(".slides-wrapper");
  const dots = document.querySelectorAll(".dot");

  if (slidesWrapper && dots.length > 0) {
    showSlide(slideIndex);

    // Event delegation for navigation controls
    const prevButton = document.querySelector(".prev");
    const nextButton = document.querySelector(".next");

    if (prevButton) {
      addTrackedEventListener(prevButton, "click", () => changeSlide(-1));
    }
    if (nextButton) {
      addTrackedEventListener(nextButton, "click", () => changeSlide(1));
    }

    // Event delegation for dot navigation
    dots.forEach((dot, index) => {
      addTrackedEventListener(dot, "click", () => currentSlide(index));
      // Add keyboard support for Enter and Space keys
      addTrackedEventListener(dot, "keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          currentSlide(index);
        }
      });
    });

    // Set up MutationObserver to detect when slideshow is removed from DOM
    // This handles SPA-style navigation (e.g., MkDocs Material instant loading)
    if (slideshowContainer) {
      mutationObserver = new MutationObserver((mutations) => {
        // Check if slideshow container was removed
        if (!document.body.contains(slideshowContainer)) {
          cleanupSlideshow();
        }
      });

      // Observe the document body for child list changes
      mutationObserver.observe(document.body, {
        childList: true,
        subtree: true,
      });
    }
  }
});

// Clean up timer on page unload (for traditional navigation)
window.addEventListener("beforeunload", cleanupSlideshow);

// Clean up on MkDocs Material navigation events (if available)
// MkDocs Material fires this event when instant loading navigates to a new page
document.addEventListener("DOMContentSwitch", cleanupSlideshow);
