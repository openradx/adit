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

ADIT (Automated DICOM Transfer) is a Swiss army knife to exchange DICOM data between various systems by using a convenient web frontend.

## Why ADIT?

Medical imaging workflows today face significant challenges when moving DICOM data between different systems. ADIT addresses these critical pain points.

## What ADIT Does

ADIT serves as a central hub for medical imaging data, connecting various DICOM systems and enabling secure, controlled data exchange with modern web technologies.

### How It Works

**ADIT acts as an intelligent bridge** between traditional DICOM systems and modern applications:

1. **Data Discovery**: Connect to multiple PACS systems and search for studies using familiar web interfaces
2. **Secure Retrieval**: Fetch DICOM data using established hospital protocols while maintaining security
3. **Privacy Protection**: Automatically pseudonymize patient data during transfer to protect privacy
4. **Format Conversion**: Convert DICOM images to NIfTI format for neuroimaging research and analysis
5. **Automated Processing**: Handle single transfers or batch operations with full audit trails

ADIT includes built-in support for converting DICOM images to **NIfTI (Neuroimaging Informatics Technology Initiative)** format, making medical imaging data accessible to a wide range of neuroimaging and research tools.

**Ready to modernize your medical imaging workflows?** ADIT bridges the gap between traditional DICOM infrastructure and modern application development, making medical imaging data as accessible as any other web API.

## About

## Developed at

[CCI Bonn](https://ccibonn.ai/) - Center for Computational Imaging, University Hospital Bonn

## Partners

- [Universitätsklinikum Bonn](https://www.ukbonn.de/)
- [Thoraxklinik Heidelberg](https://www.thoraxklinik-heidelberg.de/)
- [Universitätsklinikum Heidelberg](https://www.klinikum.uni-heidelberg.de/kliniken-institute/kliniken/diagnostische-und-interventionelle-radiologie/klinik-fuer-diagnostische-und-interventionelle-radiologie/)

!!! important "Beta Status"
ADIT is currently in early beta stage. While we are actively building and refining its features, users should anticipate ongoing updates and potential breaking changes as the platform evolves. We appreciate your understanding and welcome feedback to help us shape the future of ADIT.

## Quick Start. **Getting Started**: Learn the basics in our [getting started guide](user-docs/getting-started.md)

1. **User Guide**: Explore features in our [user guide](user-docs/user-guide.md)
2. **Development**: Contribute to the project with our [development guide](dev-docs/contributing.md)

## Getting Help

- Browse the [user documentation](user-docs/user-guide.md)
- Report issues on [GitHub](https://github.com/openradx/adit/issues)

## License

ADIT is licensed under the [AGPL-3.0-or-later](https://github.com/openradx/adit/blob/main/LICENSE) license.
