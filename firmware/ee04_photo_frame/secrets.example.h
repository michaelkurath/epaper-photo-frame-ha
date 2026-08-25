#pragma once

// Copy this file to secrets.h and fill in your local values. secrets.h is
// ignored by Git. Use the Home Assistant host's LAN address, not the Ingress
// URL shown inside the Home Assistant browser UI.
#define WIFI_SSID "YOUR_2_4_GHZ_WIFI"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define HOME_ASSISTANT_URL "http://192.168.1.10:8080"
#define DEVICE_API_TOKEN "YOUR_DEVICE_API_TOKEN"

// Keep this false for the first USB/Serial test. Set it to true only after a
// complete frame was successfully displayed; deep sleep disconnects USB.
#define ENABLE_DEEP_SLEEP false

// Zurich/central-European time including daylight-saving transitions.
#define TIME_ZONE_RULE "CET-1CEST,M3.5.0,M10.5.0/3"
