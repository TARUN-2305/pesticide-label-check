# M6 container (L4 §5). NOT BUILT on the development machine (no Docker there); the host builds it.
# The register is a build artifact (ADR-001), not in git: copy build/register.sqlite into the build context
# first, and only after the PPQS reuse permission (L4 §8, copyright gate).
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_CACHE=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY web ./web
COPY build/register.sqlite ./build/register.sqlite
RUN uv sync --locked --no-dev && useradd --uid 1000 app && chown -R app /app
USER app
EXPOSE 7860
# keys come from the host's secret settings as GROQ_API_KEY / GEMINI_API_KEY (load_keys prefers the environment)
CMD ["/app/.venv/bin/python", "-m", "labelclaim.api", "--host", "0.0.0.0", "--port", "7860", "--behind-proxy", \
     "--register", "/app/build/register.sqlite", "--web", "/app/web"]
