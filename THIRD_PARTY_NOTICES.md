# Third-party notices

This project is distributed under the MIT License, but it uses and references
third-party components that retain their own copyright and license terms.
This file identifies the direct and bundled components used by the current
prototype. It is not a replacement for the complete license files shipped by
those projects or operating-system packages.

## Bundled data

### OpenCV frontal-face Haar cascade

File:
`epaper_photo_frame/app/frame_app/data/haarcascade_frontalface_default.xml`

Source: <https://github.com/opencv/opencv/tree/4.x/data/haarcascades>

The XML file contains and retains the Intel License Agreement for the Open
Source Computer Vision Library, including the copyright notice:

> Copyright (C) 2000, Intel Corporation, all rights reserved. Third party
> copyrights are property of their respective owners.

Redistribution in source or binary form must retain or reproduce the copyright
notice, license conditions, and disclaimer. Intel's name may not be used to
endorse or promote derived products without prior written permission. The full
license text remains embedded at the beginning of the XML file.

## Home Assistant App runtime

The App directly installs or uses these components:

| Component | Role | Upstream license | Project |
| --- | --- | --- | --- |
| FastAPI | HTTP API framework | MIT | <https://github.com/fastapi/fastapi> |
| Pillow | image processing | MIT-CMU | <https://github.com/python-pillow/Pillow> |
| Uvicorn | ASGI server | BSD-3-Clause | <https://github.com/encode/uvicorn> |
| OpenCV | local face detection | Apache-2.0; bundled cascade as noted above | <https://github.com/opencv/opencv> |
| NGINX | ingress and API reverse proxy | BSD-2-Clause | <https://github.com/nginx/nginx> |
| Home Assistant base image | App container base | multiple licenses; see upstream image | <https://github.com/home-assistant/docker-base> |

Python dependencies may install additional transitive packages. The Home
Assistant base image and Alpine packages also contain their own components.
Anyone distributing a binary/container image must preserve the license
materials supplied by those packages and generate a release-specific
dependency and license inventory.

## Controller build dependencies

The firmware source expects these libraries to be installed separately in the
Arduino build environment; their source is not vendored in this repository:

| Component | Role | Upstream license | Project |
| --- | --- | --- | --- |
| Arduino core for ESP32 | ESP32-S3 platform and networking | LGPL-2.1-or-later | <https://github.com/espressif/arduino-esp32> |
| ArduinoJson | JSON parsing | MIT | <https://github.com/bblanchon/ArduinoJson> |
| Seeed_GFX | Spectra ePaper display driver; derived from TFT_eSPI | FreeBSD-style license; verify the exact installed release | <https://github.com/Seeed-Studio/Seeed_GFX> |

A distributed firmware binary must comply with the exact licenses of the
versions used to build it. In particular, the LGPL obligations of the ESP32
Arduino core and the notices from Seeed_GFX/TFT_eSPI must be reviewed for the
commercial firmware build and included with the product documentation where
required.

## Names and trademarks

Home Assistant, Google Photos, Seeed Studio, Spectra, Arduino, ESP32, and other
product names belong to their respective owners. They are used here only for
compatibility identification. No affiliation or endorsement is claimed.
