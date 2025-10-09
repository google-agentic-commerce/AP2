# How to Contribute

We would love to accept your patches and contributions to this project.

## Before you begin

### Sign our Contributor License Agreement

Contributions to this project must be accompanied by a
[Contributor License Agreement](https://cla.developers.google.com/about) (CLA).
You (or your employer) retain the copyright to your contribution; this simply
gives us permission to use and redistribute your contributions as part of the
project.

If you or your current employer have already signed the Google CLA (even if it
was for a different project), you probably don't need to do it again.

Visit <https://cla.developers.google.com/> to see your current agreements or to
sign a new one.

### Review our Community Guidelines

This project follows [Google's Open Source Community
Guidelines](https://opensource.google/conduct/).

## Development Setup

### Documentation Development

To work on the project documentation locally:

1. **Quick Start** - Use the helper script:
   ```bash
   bash scripts/serve-docs.sh
   ```

2. **Manual Setup**:
   ```bash
   # Install documentation dependencies
   python3 -m pip install -r requirements-docs.txt
   
   # Start the documentation server
   mkdocs serve
   ```

The documentation server will start at `http://127.0.0.1:8000` with live reloading enabled. Any changes you make to documentation files will automatically refresh in your browser.

### Code Development

For code contributions, see the main [README.md](README.md) for setup instructions including:
- Python environment setup
- Agent Development Kit (ADK) installation
- Sample scenarios and running instructions

## Contribution process

### Code Reviews

All submissions, including submissions by project members, require review. We
use [GitHub pull requests](https://docs.github.com/articles/about-pull-requests)
for this purpose.
