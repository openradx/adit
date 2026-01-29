---
hide:
  - toc
  - navigation
---

# **ADIT - Automated DICOM Transfer**

<div class="slideshow-container" role="region" aria-label="ADIT Screenshots Slideshow">

  <div class="slides-wrapper">
    <div class="slide">
      <img src="assets/screenshots/Screenshot01.png" alt="ADIT Screenshot 1">
    </div>
    <div class="slide">
      <img src="assets/screenshots/Screenshot02.png" alt="ADIT Screenshot 2">
    </div>
    <div class="slide">
      <img src="assets/screenshots/Screenshot03.png" alt="ADIT Screenshot 3">
    </div>
    <div class="slide">
      <img src="assets/screenshots/Screenshot04.png" alt="ADIT Screenshot 4">
    </div>
  </div>

  <button class="prev" aria-label="Previous slide">❮</button>
  <button class="next" aria-label="Next slide">❯</button>

  <div class="dot-container" role="tablist" aria-label="Slide navigation">
    <button class="dot" role="tab" aria-label="Go to slide 1" data-slide-index="0"></button>
    <button class="dot" role="tab" aria-label="Go to slide 2" data-slide-index="1"></button>
    <button class="dot" role="tab" aria-label="Go to slide 3" data-slide-index="2"></button>
    <button class="dot" role="tab" aria-label="Go to slide 4" data-slide-index="3"></button>
  </div>

  <div class="sr-only" aria-live="polite" aria-atomic="true" id="slideshow-status"></div>

</div>

ADIT acts as an intelligent bridge between traditional DICOM systems and modern applications, enabling secure, controlled, and privacy-preserving medical imaging data transfer.

Traditional PACS and DICOM systems rely on specialized protocols that are not directly compatible with modern web applications. ADIT solves this challenge by acting as a translator between web-friendly APIs and native DICOM protocols—without requiring changes to existing PACS configurations.

## Request and Response Workflow

ADIT simplifies interaction with DICOM systems through the following process:

- You send a simple web request, similar to interacting with any standard REST API.

- ADIT translates the web request into traditional DICOM commands.

- ADIT communicates with the PACS using its native DICOM protocols.

- The PACS response is converted by ADIT into a web-friendly format.

- You receive easy-to-use JSON metadata or DICOM files.

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
