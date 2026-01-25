/**
 * Slideshow functionality for ADIT landing page
 * Handles automatic cycling and manual navigation of screenshot slides
 */

// Constants
const SLIDE_INTERVAL_MS = 4000;

let slideIndex = 0;
let timer;

/**
 * Display a specific slide and update navigation dots
 * @param {number} index - The index of the slide to display
 */
function showSlide(index) {
  const slidesWrapper = document.querySelector(".slides-wrapper");
  const dots = document.querySelectorAll(".dot");

  // Guard: Exit early if slideshow markup is not present on this page
  if (!slidesWrapper || dots.length === 0) {
    return;
  }

  const totalSlides = dots.length;

  if (index >= totalSlides) slideIndex = 0;
  if (index < 0) slideIndex = totalSlides - 1;

  slidesWrapper.style.transform = `translateX(-${slideIndex * 100}%)`;

  dots.forEach((dot) => dot.classList.remove("active"));
  dots[slideIndex].classList.add("active");

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
 * Clean up timer to prevent memory leaks
 */
function cleanupSlideshow() {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
}

// Initialize slideshow when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  // Guard: Only initialize if slideshow markup exists on this page
  const slidesWrapper = document.querySelector(".slides-wrapper");
  const dots = document.querySelectorAll(".dot");

  if (slidesWrapper && dots.length > 0) {
    showSlide(slideIndex);

    // Event delegation for navigation controls
    document
      .querySelector(".prev")
      ?.addEventListener("click", () => changeSlide(-1));
    document
      .querySelector(".next")
      ?.addEventListener("click", () => changeSlide(1));

    // Event delegation for dot navigation
    dots.forEach((dot, index) => {
      dot.addEventListener("click", () => currentSlide(index));
    });
  }
});

// Clean up timer on page unload to prevent memory leaks
window.addEventListener("beforeunload", cleanupSlideshow);
