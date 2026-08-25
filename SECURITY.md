# Security Policy

## Supported versions

Security fixes are applied only to the latest version on the default branch.
This is prototype software and has not undergone an independent security
audit.

## Reporting a vulnerability

Please do not publish credentials, personal photo links, exploit details, or
other sensitive information in a public issue.

Use GitHub's private **Report a vulnerability** form in the repository's
Security tab. If that form is unavailable, open a public issue containing only
a request for a private contact channel and no technical exploit details.

Include, where possible:

- the affected version or commit;
- the affected endpoint, component, or firmware target;
- reproducible steps that do not contain real credentials or private photos;
- the potential impact; and
- any suggested mitigation.

## Prototype network boundary

The device API on port `8080` currently uses unencrypted HTTP with bearer-token
authentication. It is designed only for a trusted local network:

- do not expose port `8080` to the internet;
- do not reuse the device token for another service;
- use a random token of at least 16 characters;
- rotate the token if it may have been disclosed; and
- keep Wi-Fi credentials and `secrets.h` out of Git.

The current shared-token design is not suitable for a commercial cloud
deployment. Such a deployment requires TLS and independently revocable
credentials for every physical device.
