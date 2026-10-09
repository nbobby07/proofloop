# Build outside verification from a reviewed Python 3.11+ slim image pinned by digest.
# Example: docker build --build-arg PYTHON_BASE=python:<version>-slim@sha256:<digest> \
#   -f sandbox/Dockerfile -t proofloop-runner:local .
ARG PYTHON_BASE
FROM ${PYTHON_BASE}
COPY sandbox/requirements.lock /opt/proofloop/requirements.lock
RUN python -m pip install --no-cache-dir -r /opt/proofloop/requirements.lock
# Source, tests and runner are mounted explicitly; never COPY the repository.
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["/usr/bin/env"]
