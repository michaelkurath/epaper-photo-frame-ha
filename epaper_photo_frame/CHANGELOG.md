# Changelog

## 0.1.2 - 2026-08-25

- Avoid the AppArmor-blocked Nginx ownership change during startup.
- Send early Nginx startup diagnostics directly to standard error.



## 0.1.1 - 2026-08-24


- Run Nginx with its PID, logs and temporary files in writable locations so
  the App starts correctly under the Home Assistant container permissions.


## 0.1.0 - 2026-08-24


- Initial Home Assistant App scaffold.
- Public Google Photos adapter with paginated RPC extraction.
- SQLite catalogue, new-photo-first selection, and no immediate repeats.
- Six-colour PNG and packed 4-bit RAW output.
- Ingress dashboard plus isolated token-protected device API.

