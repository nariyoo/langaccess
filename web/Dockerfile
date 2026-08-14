# The tool opens sites in a real browser, so the image has to carry one. The Playwright image
# already has Chromium and its system libraries; installing them onto a slim Python base is the
# part that usually goes wrong.
#
# Build from the REPOSITORY ROOT, not from this directory:
#   docker build -f web/Dockerfile -t langaccess-web .
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app
COPY . /app

# pinned to the Playwright the base image was built around. A newer pip Playwright looks for a
# browser build this image does not carry, and the launch then fails with a message about a missing
# executable rather than anything about the site being audited.
RUN pip install --no-cache-dir . "playwright==1.49.0" fastapi "uvicorn[standard]"

# real Chrome rather than bundled chromium, since its fingerprint clears challenges bare chromium
# does not; the package falls back on the image's own Chromium if the channel is absent. This
# installs system Chrome through apt and has to run as root, before the user is dropped below.
# There is no `|| playwright install chromium` fallback because the image already carries a
# Chromium matching its Playwright, and installing a second copy into /root would put it where
# pwuser cannot read it.
RUN python -m playwright install chrome || true

# The base image runs as root and ships pwuser for this. Chromium as root refuses to start without
# --no-sandbox, which this package does not pass and should not, so the container would fail every
# audit; and a public service driving a browser over addresses the public supplies is the last
# thing that should hold root. PLAYWRIGHT_BROWSERS_PATH is where the image put the browsers it
# came with, readable by pwuser.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
USER pwuser

ENV LANGACCESS_TIMEOUT=120 \
    LANGACCESS_CONCURRENCY=2 \
    LANGACCESS_PER_IP_PER_HOUR=20 \
    PORT=8080

WORKDIR /app/web
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
