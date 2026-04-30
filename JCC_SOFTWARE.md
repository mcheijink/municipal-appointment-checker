# JCC Software — Appointment Booking System

## Supplier

**JCC Software** is a Dutch company with 30+ years of experience providing municipal management software to ~500 municipalities across the Netherlands, Belgium, and Germany.

- Website: [jccsoftware.nl](https://jccsoftware.nl)
- Phone: +31 (0) 541 62 70 62
- Tagline: "Let's move!"

---

## Product: JCC-Afspraken

The appointment booking system is called **JCC-Afspraken** ("JCC-Appointments"), part of the broader **JCC360°** suite:

| Module | Purpose |
|---|---|
| **JCC-Afspraken** | Appointment scheduling (this tool polls this) |
| **JCC-Klantgeleiding** | Customer flow / queue management |
| **JCC-Personeelsplanning** | Staff planning |
| **JCC-Betalen** | Payments |

The citizen-facing portal is white-labelled per municipality at `{gemeente}.mijnafspraakmaken.nl` — e.g. `enschede.mijnafspraakmaken.nl`. The product currently serves **134 municipalities** in appointment management. Current version: **4.6** (April 2026). Deployment options: SaaS or on-premise (SQL Server / Oracle).

---

## API Integration

JCC Software provides a formal **WARP API v1.0** with Swagger documentation for integration partners (partner credentials required). However, this tool does not use the official API.

### Approach: Browser-Based API Interception

Instead, `check_appointments.py` uses **Playwright** to automate a headless browser through the citizen-facing appointment portal (`{gemeente}.mijnafspraakmaken.nl`). As the browser loads the Aurelia SPA, it intercepts JSON API responses from JCC's backend.

This approach:
- ✅ Requires no credentials or API keys
- ✅ Works with the public-facing web interface
- ✅ Mirrors what a citizen would see
- ⚠️ Is fragile: SPA changes or API restructuring may break the tool

The intercepted responses contain available appointment slots in ISO 8601 format. The `_harvest_times()` function recursively extracts datetime values from the JSON structure to build a slot list.

---

## References

- [JCC-Afspraken product page](https://jccsoftware.nl/afspraken/)
- [JCC-Afspraken on GEMMA Softwarecatalogus](https://www.softwarecatalogus.nl/pakket/jcc-afspraken)
- [JCC-Afspraken WARP API (Swagger)](https://cloud-acceptatie.jccsoftware.nl/JCC/JCC_Leveranciers_Acceptatie/G-Plan/API?id=2)
