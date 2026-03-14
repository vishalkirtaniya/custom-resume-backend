# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip setuptools


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    libpq5 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    \
    # TeX Live docs and source
    && rm -rf /usr/share/texlive/texmf-dist/doc \
    && rm -rf /usr/share/texlive/texmf-dist/source \
    \
    # Unused system share directories
    && rm -rf /usr/share/doc \
    && rm -rf /usr/share/man \
    && rm -rf /usr/share/locale \
    && rm -rf /usr/share/perl \
    && rm -rf /usr/share/java \
    && rm -rf /usr/share/X11 \
    && rm -rf /usr/share/zoneinfo \
    \
    # Unused system lib directories
    && rm -rf /usr/lib/python3.13 \
    && rm -rf /usr/lib/python3 \
    && rm -rf /usr/lib/locale \
    && rm -rf /usr/lib/valgrind \
    \
    # Perl runtime libs pulled in by TeX Live — not needed at runtime
    && rm -rf /usr/lib/x86_64-linux-gnu/perl \
    && rm -rf /usr/lib/x86_64-linux-gnu/perl-base \
    && rm -rf /usr/lib/x86_64-linux-gnu/gconv \
    && rm -f  /usr/lib/x86_64-linux-gnu/libperl.so.5.40.1 \
    \
    # Var cache
    && rm -rf /var/cache/apt \
    && rm -rf /var/lib/apt

COPY --from=builder /opt/venv /opt/venv
COPY . .

RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]