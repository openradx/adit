---
hide:
  - toc
  - navigation
---

# **ADIT - Automated DICOM Transfer**

<div class="slideshow-container">
  <div class="slide fade">
    <img src="assets/screenshots/Screenshot01.png" alt="ADIT Screenshot 1">
  </div>
  <div class="slide fade">
    <img src="assets/screenshots/Screenshot02.png" alt="ADIT Screenshot 2">
  </div>
  <div class="slide fade">
    <img src="assets/screenshots/Screenshot03.png" alt="ADIT Screenshot 3">
  </div>
  <div class="slide fade">
    <img src="assets/screenshots/Screenshot04.png" alt="ADIT Screenshot 4">
  </div>
  
  
  <a class="prev" onclick="changeSlide(-1)">❮</a>
  <a class="next" onclick="changeSlide(1)">❯</a>

  <div class="dot-container">
    <span class="dot" onclick="currentSlide(1)"></span>
    <span class="dot" onclick="currentSlide(2)"></span>
    <span class="dot" onclick="currentSlide(3)"></span>
    <span class="dot" onclick="currentSlide(4)"></span>
  </div>
</div>

<style>
  
  .slideshow-container {
    position: relative;
    max-width: 100%;
    margin: 2rem auto;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  }

  .slide {
    display: none;
  }

  .slide img {
    width: 100%;
    height: auto;
  }

  .fade {
    animation: fade 1s;
  }

  @keyframes fade {
    from {opacity: 0.4}
    to {opacity: 1}
  }

  /* Navigation buttons */
  .prev, .next {
    cursor: pointer;
    position: absolute;
    top: 50%;
    width: auto;
    margin-top: -22px;
    padding: 16px;
    color: white;
    font-weight: bold;
    font-size: 18px;
    transition: 0.3s ease;
    border-radius: 0 3px 3px 0;
    user-select: none;
    background-color: rgba(0,0,0,0.5);
  }

  .next {
    right: 0;
    border-radius: 3px 0 0 3px;
  }

  .prev:hover, .next:hover {
    background-color: rgba(0,0,0,0.8);
  }

  
  .dot-container {
    text-align: center;
    padding: 10px;
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
    transition: background-color 0.3s ease;
  }

  .dot:hover, .dot.active {
    background-color: rgba(255,255,255,0.9);
  }
</style>

<script>
  let slideIndex = 1;
  let slideTimer;

  function showSlide(n) {
    let slides = document.getElementsByClassName("slide");
    let dots = document.getElementsByClassName("dot");
    
    if (n > slides.length) { slideIndex = 1 }
    if (n < 1) { slideIndex = slides.length }
    
    for (let i = 0; i < slides.length; i++) {
      slides[i].style.display = "none";
    }
    
    for (let i = 0; i < dots.length; i++) {
      dots[i].className = dots[i].className.replace(" active", "");
    }
    
    if (slides.length > 0) {
      slides[slideIndex-1].style.display = "block";
      dots[slideIndex-1].className += " active";
    }
    
    clearTimeout(slideTimer);
    slideTimer = setTimeout(() => {
      slideIndex++;
      showSlide(slideIndex);
    }, 4000); // Change image every 4 seconds
  }

  function changeSlide(n) {
    showSlide(slideIndex += n);
  }

  function currentSlide(n) {
    showSlide(slideIndex = n);
  }

  // Initialize when page loads
  document.addEventListener('DOMContentLoaded', function() {
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

ADIT includes built-in support for converting DICOM images to **NIfTI (Neuroimaging Informatics Technology Initiative)** format, making medical imaging data accessible to a wide range of neuroimaging and research tools. Simply enable the "Convert to NIfTI" option during selective or batch transfers, and ADIT will automatically generate research-ready NIfTI files alongside or instead of DICOM data.

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
