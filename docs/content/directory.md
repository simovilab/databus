---
icon: lucide/link
---

# URL Directory

The URL directory of Databús is organized as follows:

- **subdomains**, example: `docs.[domain]`
- **paths**, example: `[domain]/sections`

## Subdomains by service

- `[domain]`: **User interface** (Nuxt at port 3000)
- `api.[domain]`: **API** (Django at port 8000)
- `mqtt.[domain]`: **MQTT broker** (NanoMQ at port TCP 1883)
- `docs.[domain]`: **Databús documentation** (`self`) (Zensical at port 4000)
- `flows.[domain]`: **Data workflows** (Prefect at port 4200)
- `tasks.[domain]`: **Task monitoring** (Flower at port 5555) (_not implemented yet_)
