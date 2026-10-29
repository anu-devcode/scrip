FROM mcr.microsoft.com/devcontainers/python:3.13-bookworm

# Qt's GUI modules need EGL even when tests use the offscreen platform plugin.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libegl1 \
    && rm -rf /var/lib/apt/lists/*
