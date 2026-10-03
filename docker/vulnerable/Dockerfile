FROM ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 AS uv
FROM python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26 AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never
WORKDIR /build
COPY vulnerable-app/pyproject.toml vulnerable-app/uv.lock vulnerable-app/.python-version vulnerable-app/README.md ./
COPY vulnerable-app/src ./src
RUN uv sync --locked --no-dev --group build \
    && uv run --locked --no-dev --group build -- uv build --wheel --no-build-isolation \
    && uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file /runtime.txt
RUN uv venv --python /usr/local/bin/python /opt/runtime \
    && uv pip sync --python /opt/runtime/bin/python --require-hashes /runtime.txt \
    && uv pip install --python /opt/runtime/bin/python --no-deps dist/*.whl \
    && uv pip check --python /opt/runtime/bin/python

FROM python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26 AS runtime
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --from=build /opt/runtime /opt/runtime
ENV PATH="/opt/runtime/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt
USER 10001:10001
EXPOSE 8000
STOPSIGNAL SIGTERM
CMD ["gunicorn", "--no-control-socket", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "30", "--graceful-timeout", "15", "--worker-tmp-dir", "/tmp", "--access-logfile", "-", "--error-logfile", "-", "vulnlab_vulnerable:create_app()"]
