# Home Assistant integration

Entities are created programmatically against the HA REST/WebSocket API (needs a
long-lived token):

- **camera.goes19_ir_loop** — a *Generic Camera* config entry whose still URL is the
  animated GIF (`http://10.10.0.11:8099/loop.gif`), so it animates through HA's camera
  proxy (works remotely). Rename entity via `ha_wslib.py` -> `config/entity_registry/update`.
- **sensor.goes_wx_kmob** — pushed by `../lxc-goes-proc/emwin_alerts.py` via
  `POST /api/states/...`; new life-safety warnings fire `persistent_notification.create`
  and a `goes_wx_warning` event.

`ha_wslib.py` is a dependency-free HA WebSocket client (list/get/save dashboards,
entity registry updates). `dashboard-cards.yaml` holds the Lovelace cards.
