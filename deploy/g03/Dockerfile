FROM ghcr.io/astral-sh/uv:0.12.1@sha256:cf4eedcaa81655197f625739489effcbe71b61ceb1506f332c3facae5deceded AS uv
FROM python:3.13.11-slim-bookworm@sha256:20080e807bfc404f8450b185cf0fc95d553462673598549613735f70a5b4d5d0

COPY --from=uv /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --group cloud --no-install-project

COPY src ./src
COPY config/gcp.toml ./config/gcp.toml
COPY specs/refundacao_gcp_first/g03_parquet_cloud_run/selection.json \
    ./specs/refundacao_gcp_first/g03_parquet_cloud_run/selection.json

RUN uv sync --locked --no-dev --group cloud \
    && useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin falando-nela \
    && chmod 0444 /app/config/gcp.toml \
        /app/specs/refundacao_gcp_first/g03_parquet_cloud_run/selection.json \
    && mkdir -p /tmp/falando-nela/operations \
    && chown -R falando-nela:nogroup /tmp/falando-nela

USER 10001:65534

ENTRYPOINT ["/app/.venv/bin/falando-nela"]
CMD ["parquet-pilot", "--help"]
