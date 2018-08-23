This is support code for a medium article publication:
<a href="https://medium.com/@shahamfarooq/digi-lighter-digitize-your-highlights-5fa905d0b4f4">Digi-lighter</a>

The project involves 2+1 fundamental modules: Image Processing (contours, colour detection, etc.) and OCR (Optical Character Recognition) — the extra module is the Web side to make this user-friendly and store the information.

# OCR — Optical Character Recognition
Since digitizing characters is an old problem and one that’s been widely attacked by the tech world, there is no need to re-invent or attempt a custom version. I simply used Google’s Vision API.

# Image Processing
I used OpenCV’s Python library. This involved OpenCV’s built-in contouring methods (which as we’ll see, didn’t quite do the trick even with some custom tweaks), and overall handling of images.

# Web
Since I was using Python anyways, the easiest option was to use Flask. I also used EverNote’s API to automatically create notes for users and save highlight extractions in their notebooks.
