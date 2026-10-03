# Test tooling only; application images and dependencies remain unchanged.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble@sha256:72bd171a9ffc2b4b59532aaa6210e21014d07093120dc25528870c0b840da1f0
COPY requirements.txt /opt/browser/requirements.txt
RUN pip install --no-cache-dir --no-deps -r /opt/browser/requirements.txt && pip check
COPY sandbox_probe.py /opt/browser/sandbox_probe.py
COPY network_policy.py sandbox_result.py witnesses.py /opt/browser/
USER pwuser
ENV HOME=/tmp/browser-home
WORKDIR /tmp
ENTRYPOINT ["python", "/opt/browser/sandbox_probe.py"]
