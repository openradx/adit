/**
 * Slideshow functionality for ADIT landing page
 * Handles automatic cycling and manual navigation of screenshot slides
 */

let slideIndex = 0;
let timer;

/**
 * Display a specific slide and update navigation dots
 * @param {number} index - The index of the slide to display
 */
function showSlide(index) {
  const slidesWrapper = document.querySelector(".slides-wrapper");
  const dots = document.querySelectorAll(".dot");
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
  }, 4000);
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

// Initialize slideshow when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  showSlide(slideIndex);
});
