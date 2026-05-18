# Security and Publishing Notes

This repository is intended as a safe source-code version of Local Support AI.

Before publishing or sharing the repository, do not include:

- real customer messages, screenshots, or support conversations;
- personal data;
- internal company process details;
- local SQLite databases;
- local settings files;
- PyInstaller `build/` and `dist/` folders;
- generated executables;
- OCR/model caches;
- private style examples.

Use only synthetic or anonymized examples.

The project is a local prototype for working with test support requests. It does not require cloud inference and blocks non-local network calls inside the Python process.
