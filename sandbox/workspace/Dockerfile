# Curated build context only. Candidate source is never run by the builder.
ARG PYTHON_BASE
FROM ${PYTHON_BASE} AS runtime
COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir -r /tmp/requirements.lock

FROM runtime AS target
USER 0:0
RUN mkdir -p /jail/usr /jail/etc /jail/tmp /jail/app /jail/opt/ui && \
    cp -a /usr/local /jail/usr/local && cp -a /usr/lib /jail/usr/lib && \
    cp -a /lib /jail/lib && cp -a /etc/ld.so.cache /jail/etc/ld.so.cache && \
    if [ -e /lib64 ]; then cp -a /lib64 /jail/lib64; fi && \
    chmod 1777 /jail/tmp && touch /outside-marker
COPY launcher.py /opt/launcher.py
COPY app.py /jail/app/app.py
COPY index.html /jail/opt/ui/index.html
ENTRYPOINT ["python", "-I", "/opt/launcher.py"]

FROM runtime AS tester
USER 10002:10002
COPY protocol.py tester.py /opt/tester/
COPY job.json /opt/job/job.json
ENTRYPOINT ["python", "-I", "/opt/tester/tester.py"]
