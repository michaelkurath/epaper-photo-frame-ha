FROM ghcr.io/home-assistant/base:3.23

ARG BUILD_VERSION=0.1.0
ARG BUILD_ARCH

RUN apk add --no-cache nginx python3 py3-pip \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
        "fastapi~=0.116.0" \
        "Pillow~=11.3.0" \
        "uvicorn~=0.35.0"

COPY app /opt/epaper-photo-frame
COPY rootfs /

RUN chmod a+x \
      /etc/services.d/epaper-photo-frame/run \
      /etc/services.d/nginx/run \
    && mkdir -p /run/nginx

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="${BUILD_ARCH}" \
  org.opencontainers.image.title="Home Assistant App: ePaper Photo Frame" \
  org.opencontainers.image.description="Google Photos to Spectra 6 photo-frame service" \
  org.opencontainers.image.source="https://github.com/michaelkurath/epaper-photo-frame-ha" \
  org.opencontainers.image.licenses="MIT"
