---
hide:
  - toc
  - navigation
---

# **ADIT - Automated DICOM Transfer**

<div class="slideshow-container">

  <div class="slides-wrapper">
    <div class="slide">
      <img src="assets/screenshots/Screenshot01.png" alt="RADIS Screenshot 1">
    </div>
    <div class="slide">
      <img src="assets/screenshots/Screenshot02.png" alt="RADIS Screenshot 2">
    </div>
    <div class="slide">
      <img src="assets/screenshots/Screenshot03.png" alt="RADIS Screenshot 3">
    </div>
    <div class="slide">
      <img src="assets/screenshots/Screenshot04.png" alt="RADIS Screenshot 4">
    </div>
  </div>

<a class="prev" onclick="changeSlide(-1)">❮</a>
<a class="next" onclick="changeSlide(1)">❯</a>

  <div class="dot-container">
    <span class="dot" onclick="currentSlide(0)"></span>
    <span class="dot" onclick="currentSlide(1)"></span>
    <span class="dot" onclick="currentSlide(2)"></span>
    <span class="dot" onclick="currentSlide(3)"></span>
  </div>

</div>

<style>
  .slideshow-container {
    position: relative;
    max-width: 100%;
    margin: 2rem auto;
    overflow: hidden;
    border-radius: 8px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.15);
  }

  .slides-wrapper {
    display: flex;
    transition: transform 0.6s ease-in-out;
    width: 100%;
  }

  .slide {
    min-width: 100%;
  }

  .slide img {
    width: 100%;
    display: block;
  }

  /* Navigation buttons */
  .prev, .next {
    cursor: pointer;
    position: absolute;
    top: 50%;
    padding: 12px;
    color: white;
    font-size: 18px;
    background-color: rgba(0,0,0,0.5);
    user-select: none;
    transform: translateY(-50%);
    border-radius: 3px;
  }

  .next {
    right: 10px;
  }

  .prev {
    left: 10px;
  }

  .prev:hover, .next:hover {
    background-color: rgba(0,0,0,0.8);
  }

  /* Dots */
  .dot-container {
    text-align: center;
    position: absolute;
    bottom: 10px;
    width: 100%;
  }

  .dot {
    cursor: pointer;
    height: 12px;
    width: 12px;
    margin: 0 4px;
    background-color: rgba(255,255,255,0.5);
    border-radius: 50%;
    display: inline-block;
  }

  .dot.active {
    background-color: rgba(255,255,255,0.9);
  }
</style>

<script>
  let slideIndex = 0;
  let timer;

  function showSlide(index) {
    const slidesWrapper = document.querySelector(".slides-wrapper");
    const dots = document.querySelectorAll(".dot");
    const totalSlides = dots.length;

    if (index >= totalSlides) slideIndex = 0;
    if (index < 0) slideIndex = totalSlides - 1;

    slidesWrapper.style.transform = `translateX(-${slideIndex * 100}%)`;

    dots.forEach(dot => dot.classList.remove("active"));
    dots[slideIndex].classList.add("active");

    clearTimeout(timer);
    timer = setTimeout(() => {
      slideIndex++;
      showSlide(slideIndex);
    }, 4000);
  }

  function changeSlide(n) {
    slideIndex += n;
    showSlide(slideIndex);
  }

  function currentSlide(n) {
    slideIndex = n;
    showSlide(slideIndex);
  }

  document.addEventListener("DOMContentLoaded", () => {
    showSlide(slideIndex);
  });
</script>

ADIT acts as an intelligent bridge between traditional DICOM systems and modern applications, enabling secure, controlled, and privacy-preserving medical imaging data transfer.

Traditional PACS and DICOM systems rely on specialized protocols that are not directly compatible with modern web applications. ADIT solves this challenge by acting as a translator between web-friendly APIs and native DICOM protocols—without requiring changes to existing PACS configurations.

## Request and Response Workflow

ADIT simplifies interaction with DICOM systems through the following process:

- You send a simple web request, similar to interacting with any standard REST API.

- ADIT translates the web request into traditional DICOM commands.

- ADIT communicates with the PACS using its native DICOM protocols.

- The PACS response is converted by ADIT into a web-friendly format.

- You receive easy-to-use JSON metadata or DICOM files.

## About

## Developed at

[CCI Bonn](https://ccibonn.ai/) - Center for Computational Imaging, University Hospital Bonn

## Partners

- [Universitätsklinikum Bonn](https://www.ukbonn.de/)
- [Thoraxklinik Heidelberg](https://www.thoraxklinik-heidelberg.de/)
- [Universitätsklinikum Heidelberg](https://www.klinikum.uni-heidelberg.de/kliniken-institute/kliniken/diagnostische-und-interventionelle-radiologie/klinik-fuer-diagnostische-und-interventionelle-radiologie/)

!!! important "Beta Status"
ADIT is currently in early beta stage. While we are actively building and refining its features, users should anticipate ongoing updates and potential breaking changes as the platform evolves. We appreciate your understanding and welcome feedback to help us shape the future of ADIT.

**Admin Guide**: Explore system administration, configuration, and management features in the [Admin Guide](user-docs/admin-guide.md)

**User Guide**: Explore the application’s features, and how to execute common workflows in a clear and practical manner in our [User Guide](user-docs/user-guide.md)
