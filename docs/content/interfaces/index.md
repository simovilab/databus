---
icon: lucide/plug
description: Overview of Databús's four external interface surfaces — REST API, MQTT telemetry, AMQP events, and GTFS Realtime feeds — all served behind a single Traefik reverse proxy.
---

# Interfaces

Databús exposes four external interface surfaces and serves all of them from
behind a single Traefik reverse proxy in production.

| Page | Surface | Audience |
| --- | --- | --- |
| [REST API](rest-api.md) | HTTP/JSON — control plane and schedule data | Frontends, dispatchers, simulators |
| [MQTT telemetry](mqtt-telemetry.md) | MQTT — vehicle telemetry ingestion | On-board equipment, simulators |
| [AMQP events](amqp-events.md) | AMQP — domain event bus | Internal services, future consumers |
| [GTFS Realtime feeds](gtfs-rt-feeds.md) | Protobuf/JSON — live transit data | Passenger apps, agencies, aggregators |
| [URL directory](url-directory.md) | Subdomains and ports reference | Operators, integrators |

**Quick orientation:**

- To send vehicle position data → [MQTT telemetry](mqtt-telemetry.md)
- To create or update a run → [REST API](rest-api.md)
- To consume live vehicle locations → [GTFS Realtime feeds](gtfs-rt-feeds.md)
- To find a service URL → [URL directory](url-directory.md)
