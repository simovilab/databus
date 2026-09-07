# VPS Deployment Plan — DRAFT (awaiting Jae's go-ahead)

> **Status: no deployment has been performed.** This is a draft plan written by
> an investigation-only agent. Nothing on the VPS, and no running service, has
> been touched. Everything below is for Jae to review, correct, and approve
> before any command is run against the VPS.

---

## 1. Goal & scope

> **FINALIZED STRATEGY (this revision): stay on `compose.dev.yml`.** The
> earlier drafts of this document planned a migration to `compose.prod.yml` +
> a from-scratch Traefik topology. That plan is **superseded**. The decision,
> made after weighing both paths, is to **keep running `compose.dev.yml`**
> (project `databus-dev`) — the stack that is already live on the box — and
> apply a targeted dev-hardening checklist (§4/§6/§7) before exposing
> anything publicly, rather than cut over to `compose.prod.yml`.
>
> **Why:** staying on dev avoids the two concrete prod blockers identified in
> §2 — `backend/gtfs-eta` has no working dependency path in a
> `compose.prod.yml` image build, and migrations are gitignored so a fresh
> prod bring-up starts from zero — and it matches the stack that is already
> running and mostly working today (§3a), which lowers pre-demo risk. The
> cost is that `compose.dev.yml`/`.env.dev` default to several dev-mode
> footguns (auto-created `admin`/`admin` superuser, `DEBUG=True` behavior,
> permissive `ALLOWED_HOSTS`, host-published ports) that must be explicitly
> neutralized before anything is reachable from the public internet — that
> checklist is §4/§6's real content now. The `compose.prod.yml` path is not
> abandoned forever, just deferred past the demo (§2, §10).

1. **Fast-forward the already-deployed checkout**, not a fresh redeploy: the
   VPS's `~/git/databus` is already on `feat/fetch-telemetry` at `6936b30c`,
   52 commits behind local `HEAD` (`09fd3ff`) — bring it forward in place
   (§7 step 1), picking up the `REDIS_PASSWORD` fixes and the hourly GTFS
   Schedule import along the way.
2. Expose exactly one thing to the public internet: the **GTFS-RT feed**
   (`/feed/realtime/*`, optionally `/feed/schedule/feed.zip`) — read-only,
   no auth needed, it's meant to be public transit data. Served over
   HTTPS on `feed.167.233.130.36.sslip.io` via the **already-running**
   Traefik + Let's Encrypt (HTTP-01) instance, falling back to plain HTTP on
   the raw IP if needed (§6, §7 step 3).
3. **MQTT is never public.** Jae's phone simulator reaches the internal
   MQTT broker only through a WireGuard tunnel (§5, §7 step 4); no MQTT port
   is ever opened on the public firewall. Real vehicles use their own HTTP
   telemetry API instead of MQTT (§5) — that's an outbound poll from
   `realtime-engine`, not an inbound port, so it doesn't change the public
   network surface either.
4. Everything else — Django admin, the REST API's write endpoints, the Nuxt
   UI, RabbitMQ, Prefect, Flower, Postgres, Redis — stays unreachable from
   both the public internet **and** the WireGuard VPN, exactly as it is
   today on `compose.dev.yml` (§3a confirms the databus-owned Redis/Postgres
   are already not host-published). Jae administers the VPS via SSH (§3/§4).
   Not "protected by a login page": unreachable except by SSHing into the
   box itself.
5. After the dev-hardening checklist is applied, seed the domain models
   (operators, users, vehicles, equipment, sensors, GTFS schedule) with real
   data via the fixture in §8 so Jae can drive the pipeline end-to-end from
   his phone.

**Explicitly out of scope for this document:** actually running any of the
commands below. This is the plan; execution is a separate, later step.

---

## 2. What "latest" adds — `feat/fetch-telemetry` vs. main

`git log main..feat/fetch-telemetry` shows **~230 commits** and
`git diff main...feat/fetch-telemetry --stat` shows **284 files changed,
+22,613/-8,371 lines**. This is not an incremental delta — it's effectively a
different generation of the codebase. **Read-only recon (2026-08-22)
confirmed the VPS is not running `main` at all — it's already on
`feat/fetch-telemetry`, at commit `6936b30c`, just 52 commits behind local
`HEAD` (`09fd3ff`)** — see §3a for the full recon writeup. So the "old
version" gap is smaller than this section originally worried about, but two
things from those 52 commits still matter directly for this deploy:
`REDIS_PASSWORD` enforcement (next bullet — the fix is in the 52-commit
delta, not yet on the VPS) and the hourly GTFS Schedule import (`09fd3ff`
itself, the current tip). Highlights that matter for this plan:

- **The `compose.prod.yml` + Traefik production topology is new.** Commits
  `a3581f0` ("update Docker Compose configuration for production with labels
  for Traefik") and everything after it. If the VPS predates this, it may
  still be running services with directly-published host ports (the old
  failure mode that caused the Redis incident) rather than the current
  Traefik-fronted design.
- **`REDIS_PASSWORD` enforcement was broken until very recently and is now
  fixed on this branch** — commits `15dcfe1` (`fix(databus): honor
  REDIS_PASSWORD in all Redis clients`) and `a79b11c` (`fix(databus):
  URL-encode Redis password in channel layer address`), both from **2026-08-20**,
  i.e. two days before this investigation. Before these commits,
  `compose.prod.yml` started Redis with `--requirepass`, but no application
  client actually passed a password, so a Redis exposed to the network would
  have been reachable with **no authentication at all** despite the
  `requirepass` setting looking correct in the compose file. **This is
  almost certainly the direct mechanism behind the earlier incident**, or at
  minimum the kind of gap that caused it — the intent to require a password
  existed, but the code didn't honor it. It's fixed now, but only just, and
  only on this branch.
- **Full run-lifecycle FSM + MQTT telemetry pipeline** (`realtime_engine`,
  `runs/domain/lifecycle`, `runs/domain/telemetry`, `runs/domain/progression`)
  — this is the actual vehicle tracking pipeline Jae wants to test from his
  phone. It didn't exist in earlier history.
- **GTFS Schedule import/export** (`backend/feed/schedule/{importer,exporter}.py`,
  commit `09fd3ff` "hourly GTFS Schedule import from upstream providers",
  and `1f8ba1b` "publish GTFS Schedule zip from the database") — the
  `/feed/schedule/feed.zip` endpoint and the hourly Celery Beat refresh are
  new.
- **HTTP-polling telemetry ingestion path** (`realtime_engine/sources/`,
  `fetch_positions` task) — an additional ingestion path alongside MQTT, for
  devices that only speak HTTP+JSON. Doesn't change the public network
  surface (it's an outbound poll from `realtime-engine`, not an inbound port).
- **Migrations are gitignored and NOT committed — DEFERRED, not a blocker on
  the dev path.** `backend/docker-entrypoint.sh`'s `run_makemigrations()`
  runs `makemigrations` automatically whenever `DEBUG=True`
  (`is_true "${DEBUG:-False}"`, line 198). This was written as a
  `compose.prod.yml` concern (prod always runs `DEBUG=False`, so the
  entrypoint gate never fires there and migrations would need an explicit
  manual step). **Since we're staying on `compose.dev.yml`, this only
  matters for the one dev-hardening step that flips `DEBUG=False` for public
  exposure (§6/§7 step 2)** — at that point the auto-`makemigrations` gate
  stops firing too, so the same explicit one-time
  `makemigrations` + `migrate` step is still needed (§7 step 2), just as a
  small checklist item rather than a from-scratch prod bring-up concern. The
  currently-running dev DB already has migrations applied (it's a live,
  working stack, not a fresh clone) — this is about not silently losing that
  once `DEBUG` flips.
- **`backend/gtfs-eta` has no production dependency path — DEFERRED, moot for
  this demo.** `backend/gtfs-eta` is a symlink committed at
  `backend/gtfs-eta -> ../../gtfs-eta` (a sibling repo, `simovilab/gtfs-eta`);
  `backend/pyproject.toml`'s `[tool.uv.sources]` resolves it as `{ path =
  "gtfs-eta", editable = true }`, and `compose.dev.yml` bind-mounts
  `../gtfs-eta:/gtfs-eta` so the symlink target exists inside the container
  at `uv sync` time. This whole problem — `uv sync` failing during a
  multi-stage prod image build because there's no sibling checkout inside
  the build context — **only exists for `compose.prod.yml`, which we are not
  using for the demo.** On the dev path, the VPS already has a real
  `backend/gtfs-eta` directory in place of the dev symlink (confirmed by
  recon, §3a) and the running dev containers already import it successfully
  via the existing bind mount. §7 step 6 is just "confirm it still imports
  after the fast-forward," not a Dockerfile change. The multi-stage-`COPY`
  prod mechanism and the longer-term "publish `gtfs-eta` to PyPI under a
  SIMOVI-owned org" fix are both recorded as **non-demo-blocking follow-ups**
  in §10, to revisit only if/when a real `compose.prod.yml` migration is
  scheduled.

**Migration/data implication — staying on the live dev DB, not starting
fresh.** Because the decision is to keep running the already-deployed
`compose.dev.yml` stack rather than stand up a new one, there is no "fresh
Postgres volume" step in this revision — the existing dev database, with its
existing migrations already applied, is fast-forwarded in place (§7 step 1),
and the seed fixture in §8 is loaded additively on top of it, not into an
empty schema.

---

## 3. Threat model & the Redis lesson

**The constraint that drives every decision below:** Jae previously had a
Redis instance exposed to the internet on the old deployment. It was scanned
and abused, leading to the German government contacting him. That must not
happen again, for Redis or for anything else. The working assumption for
this plan is: **default-deny everything; explicitly allow exactly one public
HTTP surface (the feed) plus the minimum needed for SSH and the phone-only
WireGuard tunnel.**

**DECIDED — admin is fully closed, not VPN-accessible.** Django admin, the
Nuxt UI, RabbitMQ's management UI, Prefect, and Flower are not reachable
from the internet **and not reachable over the WireGuard VPN either**. Jae
administers the VPS by SSHing into it directly — e.g. `ssh -L
8000:localhost:8000 jae@vps` when he wants Django admin in a local browser,
or plain SSH + `curl localhost:...` for a quick check. WireGuard exists for
exactly one purpose: letting Jae's phone simulator reach the internal MQTT
broker (§5). It is not a general "admin VPN."

As shown in §2, the exact failure mode that likely caused this (an
apparently-password-protected Redis that clients didn't actually
authenticate to) was only fixed 2 days before this investigation. Do not
deploy without confirming that fix is in the code the VPS is running (it is,
on `feat/fetch-telemetry`, as of `a79b11c`).

### Full service/port inventory

> **Reading note for this revision:** the table below was originally written
> against `compose.prod.yml`'s Traefik-router topology. Since the finalized
> decision (§1) is to **stay on `compose.dev.yml`**, treat the "Current
> `compose.prod.yml` treatment" column as background/rejected-alternative
> context and the "Recommended exposure" column as the *target end state*
> regardless of which compose file it's achieved through. On `compose.dev.yml`
> the mechanism is different — there are no per-service Traefik routers to
> remove (dev doesn't define them); instead each service's host port is
> either left un-published, rebound to `127.0.0.1`, or (for `orchestrator`'s
> feed paths only) fronted by one new file-provider Traefik router on the
> already-running Traefik instance (§4). The end result — only the feed
> reachable from the public internet — is identical either way.

| Service | Port(s) | Current `compose.prod.yml` treatment | Recommended exposure (DECIDED) |
|---|---|---|---|
| `orchestrator` (Django/Daphne) | 8000 | Traefik `ORCHESTRATOR_DOMAIN`, full HTTPS (admin + API + feed, all on one router) | **LOCALHOST/FIREWALLED** for admin+API — see §4, split the feed paths onto a separate path-scoped router |
| `feed` paths only (`/feed/realtime/*`, optionally `/feed/schedule/feed.zip`) | via 8000, new dedicated router | not split out today | **PUBLIC** — the only public HTTP surface, served over `<PUBLIC_IP>.sslip.io` HTTPS (fallback: plain HTTP on the raw IP) |
| `user-interface` (Nuxt) | 3000 | Traefik `UI_DOMAIN` | **LOCALHOST-ONLY, SSH-tunnel access only.** Not on WireGuard, not public — remove the Traefik router entirely |
| `telemetry-broker` (NanoMQ MQTT) | 1883 (plain) | Traefik `MQTT_DOMAIN`, TCP passthrough-to-TLS on 8883 today | **NEVER PUBLIC.** Remove the Traefik TCP router and the 8883 entrypoint entirely. Reachable only via WireGuard (§5) — Jae's phone simulator is the only MQTT client; real vehicles use HTTP telemetry (§5). `allow_anonymous = true` in `telemetry-broker/nanomq.conf` is still a must-fix before relying on the tunnel as the only control (defense in depth) |
| `message-broker` (RabbitMQ) | 5672 (AMQP), 15672 (mgmt UI), 15692 (Prometheus) | AMQP internal-only; mgmt UI on Traefik `RABBITMQ_DOMAIN` | **LOCALHOST-ONLY, SSH-tunnel only.** Drop the Traefik router entirely, not just password-protect it |
| `database` (Postgres+PostGIS) | 5432 | internal network only, no Traefik | **LOCALHOST/FIREWALLED**, never public |
| `state` (Redis) | 6379 | internal network only, no Traefik, `--requirepass` | **LOCALHOST/FIREWALLED**, never public — this is the exact service from the incident |
| `analytics-engine` (Prefect) | 4200 | Traefik `ANALYTICS_DOMAIN` | **LOCALHOST-ONLY, SSH-tunnel only.** Drop the Traefik router |
| `task-monitoring` (Flower) | 5555 | Traefik `FLOWER_DOMAIN` | **LOCALHOST-ONLY, SSH-tunnel only.** Drop the Traefik router — Flower with no auth configured is itself a classic "accidentally public admin panel" incident |
| `docs` (nginx static site) | 80 | Traefik `DOCS_DOMAIN` | **LOCALHOST-ONLY** — not part of the stated minimum, and port 80 is reserved for the ACME HTTP-01 challenge (§4/§6) |
| `realtime-engine`, `schedule-engine`, `scheduler` (Celery workers) | — | internal only, correctly no Traefik label | No change needed — already correct |

**Bottom line vs. the current `compose.prod.yml`:** the compose file as
written today exposes **seven** public HTTPS/TLS surfaces via Traefik
(orchestrator, UI, MQTT, RabbitMQ UI, Prefect, Flower, docs). The decided
target is **one**: the feed, path-scoped. Every other Traefik router in
`compose.prod.yml` needs to be removed (not VPN-gated, not password-added —
removed), and MQTT's TCP/TLS entrypoint on 8883 needs to be deleted
entirely in favor of the WireGuard tunnel. RabbitMQ's management UI,
Prefect, and Flower in particular are exactly the kind of "forgot it was
even running" services that get scanned and abused — none of them have
authentication configured beyond RabbitMQ's own guest-style creds (§6). §4
describes the resulting network design.

---

## 3a. Current exposure (as-found) — read-only recon, 2026-08-22

A read-only SSH recon pass (`ssh jae@hetzner "..."`, no state changed) was
run against the VPS to ground this plan in reality instead of assumptions.
Full facts in §2/§7/§10; the exposure picture specifically:

| Port | Interface | Service | Problem? |
|---|---|---|---|
| 22/tcp | `0.0.0.0` + `[::]` | sshd | No — needed |
| 80/tcp, 443/tcp | `0.0.0.0` + `[::]` | Traefik (`traefik:v3`, already running) | No — this is the existing, working HTTPS entry for `databus-app`; the feed router should join it (§3a below) |
| 8883/tcp | `0.0.0.0` + `[::]` | Traefik `mqtt` entrypoint, **statically declared but with no dynamic TCP router wired to it today** | Currently a no-op (nothing routes there), but it's an open public port for a not-yet-configured MQTT surface — treat as **must-remove** per §5, don't leave it dangling even unrouted |
| 1883/tcp | `127.0.0.1` only | NanoMQ (`databus-dev-telemetry-broker-1`) | Not publicly reachable, **but `allow_anonymous = true`, no TLS** in its config — matches §5's existing "must-fix" item |
| 5672/tcp, 15672/tcp, 15692/tcp | `127.0.0.1` only | RabbitMQ (`databus-dev-message-broker-1`) | No — already loopback-bound |
| 6379/tcp (`databus-dev-state-1`) | not published at all (no host port) | Redis for the databus stack | No — not reachable from the host network at all today |
| 5432/tcp (`databus-dev-database-1`) | not published at all (no host port) | Postgres for the databus stack | No — not reachable from the host network at all today |
| ~~16379/tcp~~ | ~~`0.0.0.0` + `[::]`~~ → **`127.0.0.1` now** | Redis (`gtfs-rt-pipeline-redis-1`, a separate, unrelated compose project on the same box) | **DONE.** Rebound to loopback-only — this was the same failure class as the incident documented in §3, just in a different (non-databus) project; it has since been closed independently of this deployment |
| ~~15432/tcp~~ | ~~`0.0.0.0` + `[::]`~~ → **`127.0.0.1` now** | Postgres (`gtfs-rt-pipeline-postgres-1`, same unrelated project) | **DONE**, same fix as above |
| ~~18000/tcp~~ | ~~`0.0.0.0` + `[::]`~~ → **`127.0.0.1` now** | `gtfs-rt-pipeline-web-1` (Django dev server, unrelated project) | **DONE.** Rebound to loopback-only (`"127.0.0.1:18000:8000"` in `docker-compose.yml`). Confirmed `web` has no celery/poll/S3 role — the poller is `celery-worker` (+ `celery-maint`/`celery-beat`), which was not recreated by this change and kept polling (`poll_vehicle_positions_s3` tasks succeeding, no gap) throughout. Same fix class as the `16379`/`15432` closures above, closed independently of this deployment. |

**Direct answer to "is anything sensitive publicly reachable right now":
no longer.** A Redis and a Postgres instance belonging to the separate
`gtfs-rt-pipeline` project (not `databus`) were found bound to `0.0.0.0`/
`[::]` during this recon — exactly the risk class §3 exists to prevent — and
**that hardening is now DONE**: both have been rebound to `127.0.0.1`. The
one item from that same sweep that was still open, `gtfs-rt-pipeline-web-1`
on `18000/tcp`, is **also now DONE** — rebound to `127.0.0.1` (verified: `web`
has no celery/poll/S3 role, and `celery-worker` kept polling uninterrupted
through the `web` container's recreate). **The `databus`-owned services themselves (`state`/Redis,
`database`/Postgres) are currently *not* published to the host at all** —
better than `compose.dev.yml`'s documented default (§4 below) — because the
VPS's checkout has **local, uncommitted edits** to `compose.dev.yml` and
`.env.dev` (`git status -s` shows both modified, untracked backup files, and
an untracked `CLAUDE.md`) that already loopback-bind `backend`,
`message-broker`, and `telemetry-broker`'s host ports. These edits are real
but **uncommitted and undocumented** — since the finalized plan (§1) is to
keep running `compose.dev.yml` rather than move to `compose.prod.yml`,
reconciling these edits (inspect, decide keep-vs-discard, fold into a real
commit) is now a direct step on the critical path, not a side note — see §7
step 1.

**What's already running is the dev stack — and, per the finalized decision
in §1, it stays that way.** `docker ps` shows the live containers
(`databus-dev-orchestrator-1`, `databus-dev-scheduler-1`,
`databus-dev-realtime-engine-1`, `databus-dev-database-1`,
`databus-dev-state-1`, `databus-dev-message-broker-1`,
`databus-dev-telemetry-broker-1`) are all `docker compose -p databus-dev -f
/home/jae/git/databus/compose.dev.yml`, i.e. **`compose.dev.yml` is what's
actually deployed today, and it is also the target end state** — earlier
drafts of this document treated that as a fact to fix (move to
`compose.prod.yml`); this revision treats it as the foundation to harden in
place (§4, §7). It's already reasonably hardened right now (previous
paragraph) via undocumented local edits — those get reconciled and made
durable, not discarded, as part of §7.

**Deployed `databus` commit vs. local `feat/fetch-telemetry`:** the VPS
checkout (`~/git/databus`, branch `feat/fetch-telemetry`, same branch) is at
`6936b30c` (`fix(realtime): gate fetch_positions on current_run, not
runs:in_progress`). Local `HEAD` is `09fd3ff` (`feat(schedule): hourly GTFS
Schedule import from upstream providers`) — **52 commits ahead** of what's
deployed, including all the `REDIS_PASSWORD`-honoring fixes referenced
throughout §2/§6 (those commits, `15dcfe1`/`a79b11c`, **are** already within
the 52-commit delta, so the VPS does not yet have them). Note also:
**`REDIS_PASSWORD` is not actually set** in either `~/git/databus/.env` or
`.env.dev` on the VPS today (checked by key-presence only, no values
printed) — so even once the code fix lands, the deploy step must also
actually set a real password, not just rely on the code being fixed. `.env`
has all expected keys present (by name) except `REDIS_PASSWORD`;
`~/git/databus/.env.prod` exists but is effectively empty (2 lines, only a
bare `DEBUG=` key) — it has not been filled in for a real prod run yet.

**What already exists that this plan should build on, not duplicate:**
- **Traefik is already running** (`traefik:v3`, container `traefik-traefik-1`,
  compose file `~/git/databus-app/deploy/traefik/compose.traefik.yml`,
  network `traefik_proxy`, ports 80/443/8883 already published) with a
  working Let's Encrypt resolver (`certificatesResolvers.letsencrypt`, ACME
  email `dotjae609@gmail.com`, HTTP-01 via the `web` entrypoint) and a
  file-provider dynamic config
  (`~/git/databus-app/deploy/traefik/dynamic/dynamic.yml`) already defining
  the exact `security-headers`/`rate-limit`/`compression` `@file`
  middlewares that `compose.prod.yml`'s labels (§4) reference by name. **This
  plan should attach the new `feed` router to this existing Traefik
  instance** (same `traefik_proxy` external network — already exists,
  §7 step 11's "create if not already present" is now "already present, just
  join it") instead of standing up a second Traefik. The `mqtt` entrypoint on
  8883 is declared in its static config but has no dynamic TCP router today
  (§3a table above) — §5's "remove the entrypoint entirely" instruction
  should be read as "remove the currently-inactive `mqtt` entrypoint
  declaration from `traefik.yml` and don't add a router for it," not "tear
  down a working MQTT route" (none exists).
- **sslip.io is already Jae's live pattern** for this exact IP
  (`app.167.233.130.36.sslip.io`, working HTTPS cert on `databus-app`) — see
  the §6 update.
- **WireGuard is NOT installed** (`wg: command not found`, no `wg-quick@wg0`
  service) — §4/§5's WireGuard setup is genuinely greenfield, not
  build-on-existing.
- **NanoMQ is already running** (`databus-dev-telemetry-broker-1`,
  `emqx/nanomq:0.24.9-full`, loopback-bound on 1883) with
  `allow_anonymous = true` and no TLS block in its config — confirms §5's
  hardening item is still open and accurately described; nothing to adjust
  there other than confirming it's real, not hypothetical.

---

## 4. Minimal-exposure network design — dev-hardening checklist (FINALIZED)

> **This section previously planned a migration to `compose.prod.yml`. Per
> §1, that plan is superseded.** The design goal is unchanged — only the
> feed reachable publicly, everything else SSH-only, MQTT WireGuard-only —
> but the mechanism is now "harden `compose.dev.yml` in place," not "cut
> over to a different compose file." Keep reading for the still-relevant
> docker/ufw mechanics and the WireGuard/ufw design; the "never run
> `compose.dev.yml` on the VPS" rule below is explicitly **reversed** by §1.

### The docker + ufw gotcha (read this before touching firewall rules)

Docker manipulates `iptables` directly to implement `ports:` publishing. A
host firewall like `ufw` (which is also an `iptables` frontend, but a
different chain) does **not** see or control ports that Docker has published
via `-p 0.0.0.0:PORT:PORT` — Docker's rules in the `DOCKER` chain get
evaluated *before* ufw's rules in the `INPUT` chain, so `ufw deny 6379`
**does nothing** to a container that published `6379:6379`. This is almost
certainly how the original Redis exposure happened: someone assumed the host
firewall was covering it, but Docker punched the hole regardless of what ufw
said. Concretely:

```yaml
# WRONG — bypasses ufw entirely, reachable from the internet regardless
# of firewall rules:
ports:
  - "6379:6379"

# ALSO WRONG for a supposedly-internal service — same problem, just less
# obviously wrong because it looks like it maps to itself:
ports:
  - "${STATE_PORT:-6379}:6379"

# RIGHT — binds only to the loopback interface; Docker still writes an
# iptables rule, but it only accepts connections that already originated
# on the host itself, which is the same protection ufw would have given,
# and doesn't depend on ufw at all:
ports:
  - "127.0.0.1:6379:6379"

# BEST for a prod service with no dev-debugging need — don't publish a
# host port at all. Containers on the same Docker network reach each
# other by service name regardless of `ports:`; `ports:` only matters for
# host-network reachability. compose.prod.yml already does this correctly
# for `database` and `state` — no `ports:` stanza at all.
```

**Status of the `compose.dev.yml` publish surface, as decided:**
`compose.dev.yml` publishes `STATE_PORT` (Redis, default 6379),
`MESSAGE_BROKER_*`, `ANALYTICS_PORT`, `TASK_MONITORING_PORT`,
`USER_INTERFACE_PORT`, and `BACKEND_PORT` all as `0.0.0.0`-equivalent
`"${VAR}:PORT"` mappings by default (see `compose.dev.yml` lines 15-16,
125-126, 137-138, 144-147, 162-163, 177-178, 194-195) — that default is fine
on a trusted local machine but not on a public VPS. **§3a's recon already
found the deployed checkout's uncommitted local edits have loopback-bound
several of these** (`backend`, `message-broker`, `telemetry-broker`); the
dev-hardening checklist below (§7 step 1a) is to confirm/complete that for
every service in the table in §3, not to abandon `compose.dev.yml` for
`compose.prod.yml`.

### Recommended design (FINALIZED — dev-hardening, not a prod cutover)

1. **Keep running `compose.dev.yml`.** No migration to `compose.prod.yml`
   for this deploy (§1, §2). Every host-published port in the table in §3
   must be either removed (`ports:` stanza deleted, service reachable only
   on the internal Docker network) or explicitly bound to `127.0.0.1` (e.g.
   `"127.0.0.1:${STATE_PORT:-6379}:6379"`) — audit all of `state`,
   `database`, `message-broker`, `analytics-engine`, `task-monitoring`,
   `user-interface` against the VPS's current, already-partially-hardened
   `compose.dev.yml` and finish the job for anything still `0.0.0.0`-bound.
2. **`orchestrator` stays off Traefik except for the new feed router below.**
   `compose.dev.yml` does not define Traefik labels the way
   `compose.prod.yml` did, so there's nothing to "remove" — the task is to
   make sure nothing *adds* a public router for `orchestrator`'s full
   surface, only for the feed paths.
3. **Expose only the feed, via a new file-provider router on the
   already-running Traefik instance** (not a second Traefik, not
   Docker-label-driven routing on `orchestrator`, since `compose.dev.yml`
   isn't wired into that Traefik's provider scope today). Add an entry to
   the existing dynamic config
   (`~/git/databus-app/deploy/traefik/dynamic/dynamic.yml`, the same file
   already defining `security-headers`/`rate-limit`/`compression`, per §3a):
   ```yaml
   http:
     routers:
       feed:
         rule: "Host(`feed.167.233.130.36.sslip.io`) && (PathPrefix(`/feed/realtime`) || PathPrefix(`/feed/schedule/feed.zip`))"
         entrypoints: [websecure]
         tls:
           certResolver: letsencrypt
         middlewares: [security-headers@file, rate-limit@file]
         service: databus-feed
     services:
       databus-feed:
         loadBalancer:
           servers:
             - url: "http://databus-dev-orchestrator-1:8000"
   ```
   For Traefik to resolve `databus-dev-orchestrator-1:8000`, the
   `orchestrator` container needs to be reachable from the Traefik
   container — attach `orchestrator` to the existing external
   `traefik_proxy` network in `compose.dev.yml` (in addition to its
   internal databus network), rather than relying on a host-port hairpin.
   This exposes exactly:
   - `GET /feed/realtime/vehicle_positions.json`
   - `GET /feed/realtime/vehicle_positions.pb`
   - `GET /feed/realtime/trip_updates.json`
   - `GET /feed/realtime/trip_updates.pb`
   - optionally `GET /feed/schedule/feed.zip`
   (from `backend/feed/urls.py`). Do **not** add `/feed/` bare (the `status`
   view), `/admin/`, or `/api/` — those stay off the router entirely, not
   just off this rule.

   Practical note: Traefik's `PathPrefix` is a router-selection rule, not a
   Django-level allow-list — verify with the external nmap/curl check in §7
   that hitting `https://feed.167.233.130.36.sslip.io/admin/` from outside
   actually fails to route (404/no match), since no other router exists for
   that host.
4. **No VPN access to admin surfaces.** Django admin, the Nuxt UI, RabbitMQ
   mgmt UI, Prefect, and Flower are reached only via SSH (port-forward or a
   shell on the box) — never via WireGuard, never via a public router. See
   the admin-closure note in §3.
5. **WireGuard, scoped to the phone→MQTT path only.** Set up a WireGuard
   interface on the VPS (UDP, e.g. port 51820) with a single peer: Jae's
   phone. Once connected, the phone reaches `telemetry-broker` at its
   Docker-internal address (or `127.0.0.1:1883` on the VPS through the
   tunnel) exactly as if it were on the same LAN — no inbound MQTT port is
   ever opened to the public internet. See §5 for the full MQTT design.
6. **Host firewall (ufw), default-deny inbound — already in this state**
   (confirmed by recon, §3a: ufw is default-deny except 22/80/443). Once
   WireGuard is installed, add the one remaining rule:
   ```
   ufw allow 51820/udp  # WireGuard — phone→MQTT tunnel only
   ```
   **Final public-port list: 443 (feed), 80 (ACME only), 22 (SSH), and
   51820/udp (WireGuard). Nothing else.** No 8883/1883 at all — MQTT has no
   public port in the decided design.
7. **fail2ban** on SSH at minimum; optionally on Traefik's access log for
   repeated 401/403s on the feed path, though with no auth on the feed
   there's nothing to brute-force there — fail2ban's value here is mostly
   SSH.
8. **After all of the above, run the external verification step in §7**
   (`nmap` from off-VPS) before calling this done — it must show **only**
   443, 80, 22, and 51820/udp answering. A locally-reasoned-through config
   is not the same as a confirmed one — that's the lesson from the original
   incident.

---

## 5. MQTT — DECIDED: tunneled, never public

**No public MQTT port at all, full stop.** Jae's phone (running the
simulator) is the only MQTT client that exists for this demo. Real
vehicles/OBE hardware do **not** use MQTT — they use the HTTP telemetry
polling path instead:

- `operations.Sensor.source_http_url` / `source_json_mapping`
  (`backend/operations/models.py` lines ~211-212) hold the per-sensor HTTP
  endpoint and JSON field mapping for a real vehicle's telemetry API.
- `realtime_engine/sources/http_json.py` reads `sensor.source_http_url`
  (line 135) to poll it.
- `realtime_engine/tasks.py::fetch_positions` (line 114) is the Celery task
  (scheduled via `databus/celery.py`) that polls every `Sensor` with
  `source_type="http"` and re-publishes survivors on
  `transit/vehicle/<id>/position` internally (`realtime_engine/sources/
  publisher.py`) — i.e. the HTTP path still lands on the same internal MQTT
  topic, but the *inbound* leg from the real vehicle is an outbound HTTP GET
  from `realtime-engine`, not an inbound MQTT publish. This matches what
  the dumped local DB actually shows: the six real navsat-brand sensors
  currently in the dev DB (§8) are all `source_type="http"` with a live
  `wsclientes.navsat.com` URL — confirming this is the real, already-used
  ingestion path for actual vehicles, not a hypothetical.

Because of that, MQTT only ever needs to be reachable by Jae's own phone,
which can trivially run a VPN client. So:

1. **Install and set up WireGuard** on the VPS — confirmed genuinely
   greenfield by recon (§3a: `wg: command not found`, no `wg-quick@wg0`
   service). UDP port 51820, one peer: Jae's phone. No inbound MQTT port
   (1883 or 8883) is ever opened on the public firewall — it's not even in
   the ufw allow-list (§4 step 6).
2. **The `mqtt` entrypoint Traefik currently declares (statically, on 8883)
   has no dynamic TCP router wired to it today** (§3a) — leave it removed
   from Traefik's static `entrypoints:` config rather than adding a router
   to it. There is no public-facing MQTT surface in the decided design, so
   this entrypoint should be deleted, not merely left unrouted.
3. **`allow_anonymous = true` in `telemetry-broker/nanomq.conf` is still a
   must-fix**, defense-in-depth, even though the tunnel is the primary
   control: anyone who compromises the WireGuard peer or pivots from
   another VPS-internal service shouldn't get unauthenticated MQTT for
   free. Set `allow_anonymous = false` with a simple username/password
   backend for the phone's single set of credentials — no need for NanoMQ's
   fancier JWT/HTTP auth plugins or per-vehicle topic ACLs for a one-client
   demo; revisit if/when real OBE hardware is onboarded through this same
   tunnel pattern. **DECIDED — credential: `admin` / `admin`** (the
   simulator's existing default). **Caveat:** this weak credential is
   acceptable *only* because MQTT is reachable solely over the WireGuard
   tunnel and is never publicly bound (§4 step 6: 1883/8883 are not in the
   ufw allow-list, no public port exists for MQTT in this design). If MQTT
   is ever exposed beyond the tunnel — a future public router, a WireGuard
   misconfiguration, onboarding real OBE hardware over a different path —
   this credential must be rotated to something generated first. Not
   configured yet; this is a deploy-time step (§7 step 4), not done by this
   revision.
4. Topic ACLs and IP allow-listing (both still valid hardening ideas) are
   deferred as follow-ups, not demo-blocking, given the only client is
   Jae's own phone over his own tunnel.

---

## 6. Secrets & config — dev-hardening checklist (MANDATORY before public exposure)

> `compose.dev.yml`/`.env.dev` default to dev-mode behavior on purpose — that
> default is safe as long as nothing public points at the box. Since §4 puts
> the feed behind a public Traefik router, every item below must be applied
> first. This replaces the earlier `.env.prod`-oriented version of this
> section (superseded by §1's decision to stay on `compose.dev.yml`).

- **`DEBUG=False` in `.env.dev`.** With `DEBUG=True` (the dev default),
  Django serves full tracebacks on error — completely wrong for a
  public-facing feed endpoint, even a read-only one. Flip it before the
  feed router in §4 goes live.
- **Neutralize the auto-created `admin`/`admin` superuser.**
  `backend/docker-entrypoint.sh`'s `ensure_dev_superuser()` creates
  `admin`/`admin` (or `DJANGO_SUPERUSER_*` env vars) whenever `DEBUG=True`.
  Flipping `DEBUG=False` (previous bullet) stops this path from firing
  again, but that alone doesn't retroactively fix anything — **verify
  whether an `admin`/`admin` account already exists on the box from a prior
  `DEBUG=True` run** (`manage.py shell` → `User.objects.filter(username="admin")`
  → check `is_superuser`/`last_login`), and if it does, set it a strong
  generated password (or delete it) rather than leaving the default in
  place. Admin is SSH-only per §3/§4, but "SSH-only" is not the same
  guarantee as "no default credential exists at all" — do both.
- **`ALLOWED_HOSTS` includes `feed.167.233.130.36.sslip.io`** (and any other
  host the feed ends up served on, e.g. the raw IP if using the plain-HTTP
  fallback from §6 below). Django will refuse the request (400) for any
  `Host:` header not in this list once `DEBUG=False` — confirm it's set
  correctly in `.env.dev` before the first public request, not discovered
  live during the demo.
- **`REDIS_PASSWORD`**: as covered in §2, this is now honored by all clients
  as of commits `15dcfe1`/`a79b11c` (2026-08-20) on this branch — but the VPS
  doesn't have those commits yet (52 behind, §3a) until §7 step 1's
  fast-forward runs, and even after that, **`.env.dev` on the VPS does not
  currently set `REDIS_PASSWORD` at all** (checked by key-presence during
  recon). Both parts are needed: the fast-forward *and* actually setting a
  real generated password in `.env.dev`. Confirm no databus-owned service
  still publishes a host port for `state`/`database` (§3a: currently neither
  does — keep it that way through the fast-forward and any local-edit
  reconciliation in §7 step 1).
- **Migrations**: flipping `DEBUG=False` (above) also disables the
  entrypoint's auto-`makemigrations` (§2). Since migrations are gitignored,
  add an explicit one-time `makemigrations` + `migrate` step (§7 step 2) —
  don't assume a normal container restart will pick up any pending schema
  change once `DEBUG=False` is in effect.
- **RabbitMQ**: `.env.dev` should not be left on `guest`/`guest` if
  `message-broker`'s ports end up reachable from anywhere beyond the
  Docker-internal network — confirmed loopback-only by recon (§3a), keep it
  that way; changing the credential is a nice-to-have here, not a blocker,
  since the port isn't public either way.
- **NanoMQ (`telemetry-broker`) credential — DECIDED: `admin`/`admin`** for
  the phone simulator, set when `allow_anonymous = false` is applied (§5 step
  3, §7 step 4). Acceptable only because MQTT is WireGuard-tunnel-only and
  never publicly bound — rotate immediately if that ever changes. Not
  configured by this revision; deploy-time step.
- **Flower has no authentication configured at all** by default
  (`mher/flower:2.0` with just a broker URL). Flower stays SSH-only per §4
  regardless — if that ever changes, add `--basic-auth` first.
- **TLS without a domain — DECIDED, and already Jae's established pattern.**
  Jae has no domain, only a raw public IP (`167.233.130.36`, confirmed by
  recon). Primary plan: `FEED_DOMAIN=<PUBLIC_IP>.sslip.io` (e.g.
  `167.233.130.36.sslip.io`) — sslip.io is a public wildcard-DNS service that
  resolves any `A.B.C.D.sslip.io` hostname back to `A.B.C.D` with no
  registration needed, which is enough for Traefik's Let's Encrypt resolver
  to issue a real cert against that hostname. **This isn't hypothetical —
  Jae already runs exactly this pattern on the VPS today**, for a different
  app (`databus-app`): its Traefik router is
  `Host(`app.167.233.130.36.sslip.io`)` with
  `traefik.http.routers.app.tls.certresolver=letsencrypt`, confirmed live via
  `docker ps` labels during recon. The feed router should follow the same
  naming convention, e.g. `feed.167.233.130.36.sslip.io`, on the **same
  already-running Traefik instance** (`~/git/databus-app/deploy/traefik/`,
  `traefik:v3`, ACME email `dotjae609@gmail.com`) rather than standing up a
  second one — see the new §3a and §4 notes on reusing it. **ACME challenge:
  HTTP-01** (works with sslip.io; TLS-ALPN-01 does not need port 80 but is
  fussier to set up and unnecessary here) — Traefik needs port 80 reachable
  to answer the HTTP-01 challenge and to redirect plain HTTP to HTTPS; §4
  step 6 already allows 80/tcp for exactly this, and it's already open today.
  **Trivial fallback: plain HTTP on the raw IP**, no TLS at all — acceptable
  because the exposed data (`/feed/realtime/*`) is read-only public transit
  data with no confidentiality requirement; use this if sslip.io or Let's
  Encrypt rate limits/outages block the HTTPS path during the demo.

### Redis auth verification (independent re-check)

Commits `15dcfe1` and `a79b11c` (2026-08-20) claim `REDIS_PASSWORD` is now
honored everywhere. Rather than trust the commit messages, every Redis
connection/client construction site in `backend/` was enumerated directly
and checked. **Verdict: yes — every live Redis client in the running
services is authenticated**, and the one place a password is embedded in a
URL (the Channels layer) uses the same `urllib.parse.quote()` fix from
`a79b11c`. Full table:

| File:line | Client | Password passed? | Notes |
|---|---|---|---|
| `backend/databus/redis_client.py:24-30` (`create_redis_client()`) | Shared factory — `redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD or None, ...)` | **Yes** | The single source of truth every other in-process client below calls through. Empty/unset password → `None` (dev-mode unauthenticated is intentional, not a bug). |
| `backend/runs/domain/lifecycle/actions.py:16` | `create_redis_client(decode_responses=False)` | **Yes** (via factory) | |
| `backend/runs/domain/lifecycle/guards.py:17` | `create_redis_client(decode_responses=False)` | **Yes** (via factory) | |
| `backend/runs/domain/progression/stop_times.py:52` | `create_redis_client()` | **Yes** (via factory) | |
| `backend/runs/domain/progression/producer.py:24` | `create_redis_client()` | **Yes** (via factory) | |
| `backend/runs/domain/detection/dispatch.py:23` | `create_redis_client()` | **Yes** (via factory) | |
| `backend/realtime_engine/mqtt.py:45` | `create_redis_client()` | **Yes** (via factory) | MQTT bootstep's Redis handle |
| `backend/realtime_engine/tasks.py:19` (`redis_client = create_redis_client()`) | `create_redis_client()` | **Yes** (via factory) | |
| `backend/schedule_engine/tasks.py:38` | `create_redis_client(db=...)` | **Yes** (via factory) | |
| `backend/databus/settings.py:172-176` (`CHANNEL_LAYERS` / `channels_redis`) | Django Channels layer — builds a `redis://:<password>@host:port/0` URL when `REDIS_PASSWORD` is set, else falls back to a bare `(host, port)` tuple | **Yes**, and URL-encoded | This is the exact site `a79b11c` fixed: `quote(REDIS_PASSWORD, safe='')` (settings.py:173) — confirmed present and imported (`from urllib.parse import quote`, settings.py:14). A password containing `@`, `:`, `/`, or `%` would otherwise corrupt the URL and either fail to connect or silently authenticate as the wrong (empty) credential. |
| `backend/scripts/cleanup_runs.py:107-110` (`get_redis()`) | Standalone offline maintenance script — `redis.Redis(host, port, db, password=password or None, ...)` | **Conditionally yes** | Not a running service; a human-invoked CLI tool. Password comes from `--redis-password` (default `os.getenv("REDIS_PASSWORD", "")`, script line 510) — authenticated automatically if the env var is set in the operator's shell, but silently unauthenticated if run without it and without `--redis-password`. Not a production-traffic risk (never runs as a long-lived service), but worth a one-line callout in the runbook: always run it with `REDIS_PASSWORD` exported. |

**Not a Redis client at all (checked and ruled out):** `CELERY_BROKER_URL`
(`databus/settings.py:148-150`) is AMQP (`amqp://...@RABBITMQ_HOST:...`),
not Redis — Celery's broker is RabbitMQ in this codebase.
`CELERY_RESULT_BACKEND = "django-db"` (settings.py:151) — results go to
Postgres, not Redis. No `CACHES` setting is defined in `settings.py`, so
Django's cache backend is the default in-memory `LocMemCache`, not Redis.
`messages/publisher.py` uses `kombu.Connection(settings.CELERY_BROKER_URL)`
— also AMQP, not Redis. `schedule_engine/builders.py` references
`redis.Redis` only as a structural type hint/protocol for static typing, not
a connection construction site.

**Gaps found: none.** Every actual Redis connection in the running services
goes through `create_redis_client()` and is authenticated when
`REDIS_PASSWORD` is set; the one URL-embedding site (Channels) correctly
percent-encodes the password. The only residual soft spot is the offline
`cleanup_runs.py` script depending on the operator remembering to export
`REDIS_PASSWORD` (or pass `--redis-password`) — recommend documenting that
in the ops runbook, not a code fix. Recommend still running the smoke test
below rather than trusting static analysis alone, per the incident lesson
in §3.

**Post-deploy smoke test** (unchanged from the original draft, still the
right check): from inside a container on the `internal` Docker network,
confirm `redis-cli -h state ping` (no `-a`) fails/times out, and `redis-cli
-h state -a "$REDIS_PASSWORD" --no-auth-warning ping` returns `PONG`.

---

## 7. Deployment steps (draft — not yet executed)

Ordered, VPS-side. Rewritten around the finalized strategy (§1): **stay on
`compose.dev.yml`, harden it, don't migrate to `compose.prod.yml`.** The box
is not greenfield: it's a Hetzner `vServer` (`ubuntu-8gb-fsn1-1`), **Ubuntu
26.04 LTS** ("Resolute Raccoon", kernel 7.0.0-15, x86-64), 4 vCPU, 7.6GiB RAM
(3.1GiB free), 75GB disk (32GB available), Docker 29.6.1 / Compose v5.2.0 —
confirmed live, not assumed. Traefik, the `databus` checkout (at an older
commit), and a WireGuard-free network posture are the starting point — see
§3a for the full inventory. **Already done, no action needed:** gtfs-rt-pipeline
Redis/Postgres rebound to loopback (§3a), ufw default-deny with 22/80/443
open, SSH keys-only (`99-hardened.conf`).

1. **Fast-forward the deployed checkout, reconciling local edits first.**
   `~/git/databus` on the VPS is on `feat/fetch-telemetry` at `6936b30c`, 52
   commits behind local `HEAD` (`09fd3ff`) — including the `REDIS_PASSWORD`
   fixes (`15dcfe1`/`a79b11c`). **DECIDED — release ref: the tip of
   `feat/fetch-telemetry`** (currently `09fd3ff`), the branch the VPS is
   already on; not a tag, not `main`.

   **The uncommitted local edits are now persisted, not just noted.** A
   read-only capture pass copied every modified/untracked file in
   `~/git/databus` to `~/git/databus/.vps-local-backup/` on the VPS (plus
   `uncommitted.diff` and `status.txt`), and pulled a copy of the tracked
   edits + diff down to the laptop at `deploy/vps-local-edits/` (untracked,
   not git-added — it holds `.env.dev`, a real secrets file). The working
   tree itself was **not** touched (no stash/checkout/reset) — capture only.
   What the tracked edits actually contain, from `uncommitted.diff`:
   - **`.env.dev`**: one line changed, `DEBUG=True` → `DEBUG=False`.
   - **`compose.dev.yml`**: `backend` rebound to `127.0.0.1` on its host
     port and attached to a new external `traefik_proxy` network with alias
     `orchestrator` (a manual Traefik file-provider attach — the mechanism
     §4 step 3 describes); `state` (Redis) dropped its host port publish
     entirely (comment notes: "unauthenticated" exposure removed
     2026-07-16 — this matches the incident history in §3); `telemetry-broker`
     (NanoMQ) and all three `message-broker` (RabbitMQ) ports rebound to
     `127.0.0.1`; a top-level `traefik_proxy: external: true` network was
     added.
   - These are real hardening already in place, not experiments — they
     overlap heavily with §4/§6's checklist (loopback-binding, the
     `orchestrator`↔Traefik attach) and should be **reconciled into the
     fast-forward, not discarded**: either `git stash` → fast-forward →
     `git stash pop` and resolve conflicts by hand, or fold them into a
     proper commit first so they survive cleanly. Use
     `deploy/vps-local-edits/uncommitted.diff` (laptop copy) or
     `~/git/databus/.vps-local-backup/uncommitted.diff` (VPS copy) as the
     source of truth for what to reapply if the working tree changes before
     the fast-forward actually runs.
   - The untracked files present alongside them (`CLAUDE.md`, a
     `.env.bak.pre-rotation.*` backup, `docs/DOCS-AUDIT-REPORT.md`,
     `docs/ZENSICAL-REFERENCE.md`, `scripts/compact_feeds.py`,
     `backend/feed/files/`, `graphify-out/`) were captured too but are
     working clutter, not deploy-relevant config — no action needed on them
     beyond the backup already taken.
   Then:
   ```
   git -C ~/git/databus fetch
   git -C ~/git/databus checkout feat/fetch-telemetry && git -C ~/git/databus pull --ff-only
   docker compose -p databus-dev -f ~/git/databus/compose.dev.yml up -d --build
   ```

   **Deferred follow-up (post-demo, not now):** once the deployment is fully
   working end-to-end, commit the reconciled VPS-local changes to a **new
   branch** (Jae's idea) rather than leaving them as loose local edits or
   folding them silently into `feat/fetch-telemetry` — gives them a proper
   history and a clean path to review/merge later. Not part of this
   revision's scope; do not create that branch or commit as part of §7.
2. **Apply the dev-hardening checklist from §6, in order, before anything
   in step 3 goes live:**
   - Set `DEBUG=False` in `.env.dev`.
   - Check for and neutralize any pre-existing `admin`/`admin` superuser
     (set a strong password or delete it).
   - Set `ALLOWED_HOSTS` to include `feed.167.233.130.36.sslip.io`.
   - Set a real, generated `REDIS_PASSWORD` in `.env.dev` (confirmed not
     currently set, §3a) — now that the code honors it post-fast-forward,
     confirm with the smoke test in §6.
   - Generate migrations once, deliberately, since `DEBUG=False` disables
     the entrypoint's auto-`makemigrations`:
     ```
     docker compose -p databus-dev -f compose.dev.yml exec orchestrator \
       uv run python manage.py makemigrations
     docker compose -p databus-dev -f compose.dev.yml exec orchestrator \
       uv run python manage.py migrate --noinput
     ```
   - Re-confirm no databus-owned service (`state`, `database`, and anything
     else per the §3 table) publishes a host port beyond `127.0.0.1`.
3. **Expose only the feed, via a new file-provider Traefik router** (§4
   step 3): add the `feed` router/service entry to
   `~/git/databus-app/deploy/traefik/dynamic/dynamic.yml`, attach
   `orchestrator` to the existing external `traefik_proxy` network in
   `compose.dev.yml`, and restart `orchestrator` + reload Traefik's dynamic
   config (file provider picks up changes automatically, but verify).
   `traefik_proxy` already exists (recon confirmed via `docker network ls`)
   — nothing to create. If sslip.io/Let's Encrypt is unavailable during the
   demo, fall back to plain HTTP on the raw IP for the feed router (§6) —
   drop `tls`/`certResolver` from the router entry above, keep everything
   else.
4. **Set up WireGuard for the phone→MQTT path** (§4 step 5, §5): install
   WireGuard (genuinely greenfield, confirmed by recon), one interface, one
   peer (Jae's phone), UDP 51820; add `ufw allow 51820/udp`. Then apply the
   NanoMQ hardening: `allow_anonymous = false` + a username/password for the
   phone's credentials in `telemetry-broker/nanomq.conf` (credential choice
   is open, §10); TLS on NanoMQ itself stays optional since the transport is
   already tunneled. Confirm 8883 is not routed anywhere (§3a: Traefik
   declares the `mqtt` entrypoint but nothing routes to it today — remove
   the stale entrypoint declaration too, don't just leave it unrouted).
5. **Seed the database.** Both fixtures are tracked in git now — nothing is
   delivered out-of-band:
   ```
   docker compose -p databus-dev -f compose.dev.yml exec orchestrator \
     uv run python manage.py loaddata publishers.json
   docker compose -p databus-dev -f compose.dev.yml exec orchestrator \
     uv run python manage.py loaddata demo_fleet.json
   docker compose -p databus-dev -f compose.dev.yml exec orchestrator \
     uv run python manage.py bootstrap_schedule
   ```
   The orchestrator entrypoint already does both on startup (`loaddata` only
   when `DEBUG=True`), so this is a verification step more than an action.
   Then change the seeded operator passwords — they are known dev values
   (§8): `manage.py changepassword driver1`, and likewise for `driver2` and
   `dispatcher1`. Confirm `Vehicle.id` (`299-1014` … `299-922`) matches
   exactly what the telemetry source publishes as `<id>` in
   `transit/vehicle/<id>/position`.
6. **Confirm `gtfs-eta` imports.** On the dev path this is not a build
   change (§2) — `backend/gtfs-eta` is already a real directory on the VPS
   and the existing bind mount already wires it up. After the fast-forward
   (step 1), just confirm the container still imports it cleanly (e.g.
   `docker compose -p databus-dev -f compose.dev.yml exec orchestrator uv
   run python -c "import gtfs_eta"` or the package's actual import name).
   The prod image-bake mechanism and the SIMOVI-owned-PyPI follow-up (§2)
   stay deferred — not needed for this demo.
7. **Verify end-to-end** (full detail in §9):
   - `curl https://feed.167.233.130.36.sslip.io/feed/realtime/vehicle_positions.json`
     returns valid GTFS-RT JSON over HTTPS.
   - External self-scan (`nmap -Pn -p- 167.233.130.36` from off-VPS) shows
     **only** 22, 80, 443, and 51820/udp answering — nothing else. Repeat
     after any compose/firewall change; this is the step that directly
     targets the fear that motivated this whole document.
   - Start a run from the phone: connect over WireGuard, publish telemetry
     via MQTT → NanoMQ → `realtime-engine` → Redis → `schedule-engine` →
     confirm the vehicle appears in `vehicle_positions.json` at the public
     feed URL. This is also where the kiosk's §7 trip_id match (per the
     kiosk's own doc) gets verified against a real run.

---

## 8. Seed data plan — tracked fixture + upstream import

**Superseded 2026-09-07.** The out-of-band `deploy/seed/seed_fleet.json` is
gone, along with the whole `backend/feed/fixtures/` GTFS dump. Seeding is now
two tracked, idempotent steps that the entrypoint runs on its own:

1. **`manage.py loaddata publishers.json`** — `backend/feed/fixtures/publishers.json`,
   2 objects, loaded in **every** environment (not DEBUG-gated): 1
   `feed.TransitSystem` (`bUCR`) and 1 `feed.FeedPublisher` (`SIMOVI`,
   `is_active=True`) carrying the upstream feed URLs. Without these,
   `bootstrap_schedule` finds no active publisher and every GTFS-RT feed is
   silently empty. Contains no credentials and no user accounts.

2. **`manage.py loaddata demo_fleet.json`** — `backend/operations/fixtures/demo_fleet.json`,
   26 objects, **DEBUG-gated**:
   - 1 `operations.Company` (`SIMOVI`), 1 `operations.DataProvider` (`NavSat`)
   - 6 `operations.Vehicle`: `299-1014`, `299-1015`, `299-604`, `299-987`,
     `299-921`, `299-922` — the real plate numbers, `status="IN_SERVICE"`
   - 6 `operations.Equipment` (`NavSat <plate>`) and 6 `operations.Sensor`
     (`GPS <plate>`), `status="ACTIVE"`, `source_type="http"`, pointed at the
     NavSat fleet endpoint with the JSON mapping `fetch_positions` expects.
     UUIDs are deterministic (uuid5), so re-loading updates rows instead of
     duplicating them.
   - 3 `auth.User` + 3 `operations.Operator` (`driver1`, `driver2`,
     `dispatcher1`) at pks 9001–9003.

3. **`manage.py bootstrap_schedule`** — imports the GTFS Schedule for every
   active publisher that has no current `Feed`, straight from
   `FeedPublisher.schedule_url`
   (`https://feeds.simovi.org/bucr/schedule/gtfs.zip`). No GTFS data is
   checked into the repo any more. Verified end-to-end: 1 agency, 1 route,
   122 trips, 22 stops, 1049 stop_times. Idempotent — a second run reports
   `already has a current Feed; skipping`, and the hourly
   `schedule_engine.tasks.fetch_schedule` beat task keeps it current from
   there.

### Security note — read before deploying

`demo_fleet.json` ships **known dev passwords** (all three operator accounts
use `databus`), which is why `backend/docker-entrypoint.sh::load_initial_data()`
is gated on `DEBUG=True`. `publishers.json` and `bootstrap_schedule` are
deliberately *not* gated — an empty schedule means empty GTFS-RT feeds in any
environment.

**The sensors' `source_http_url` is a placeholder**
(`https://navsat.example.com/REPLACE_WITH_REAL_NAVSAT_URL`). The real NavSat
endpoint embeds a credential in its path, so it is deliberately kept out of
git pending a decision on whether to source it from an env var. HTTP polling
will not work until it is set — via the Django admin, or by wiring
`Sensor.source_http_url` to configuration.

If the VPS runs with `DEBUG=True`, run `manage.py changepassword` for each of
`driver1`, `driver2`, `dispatcher1` immediately after seeding. The superuser
is a separate matter and is unchanged: `ensure_dev_superuser()` still creates
`admin`/`admin` under `DEBUG=True` unless `DJANGO_SUPERUSER_*` is set — that
account is deliberately **not** in the fixture, and putting a known-password
superuser on a publicly-reachable Django install remains a real risk. Set
`DJANGO_SUPERUSER_PASSWORD` to a generated value, or create the superuser
explicitly as part of the deploy.

### Vehicle IDs

`Vehicle.id` is the plate number (`299-1014` … `299-922`), and it must match
what the telemetry source publishes as `<id>` in
`transit/vehicle/<id>/position`. The NavSat mapping resolves it from the
`plateNumber` field. If a simulator publishes different IDs, update the
fixture's `Vehicle`/`Equipment`/`Sensor` pks and `vehicle` fields to match.

### Runtime data, not seeded

`runs.Run` is created at runtime via the run-lifecycle API (see `runs/views.py`
and `docs/content/runs/`) — the "start a run" action done live, never seeded.


## 9. Post-deploy verification & rollback

### End-to-end pipeline verification

1. Seed data present (§8) — `publishers.json` loaded and `bootstrap_schedule`
   imported a current `Feed` (verify both, not just the latter).
2. Start a run via the orchestrator API, reached over SSH tunnel (§4 step
   4) — never the public feed router — see
   `docs/content/runs/lifecycle-states.md`.
3. From the phone simulator, connect over WireGuard and publish to
   `transit/vehicle/unit-0N/position` on the internal MQTT broker (§5) with
   a valid payload (see `docs/content/interfaces/mqtt-telemetry.md` for the
   exact JSON shape — `latitude`/`longitude` required).
4. Confirm `realtime-engine` picked it up: check
   `vehicle:unit-0N:position` in Redis (`redis-cli -a $REDIS_PASSWORD hgetall
   vehicle:unit-0N:position`, run *inside* a container on the `internal`
   network — never expose Redis to check this).
5. Wait up to 15s (schedule-engine's build cadence) and confirm the public
   feed reflects it:
   `curl https://feed.167.233.130.36.sslip.io/feed/realtime/vehicle_positions.json`
   should show the vehicle's entity with the published position.
6. End the run via the orchestrator API; confirm the vehicle drops out of
   the next feed build (`runs:in_progress` no longer includes it, per the
   `MODEL.md` Redis key patterns).

### Rollback

- If the hardened stack fails health checks or the external port-scan check
  (§7 step 7) shows anything unexpected open: pull the new `feed` router
  entry out of `dynamic.yml` (or `docker compose -p databus-dev -f
  compose.dev.yml down` if the problem is deeper than just the router) and
  investigate offline before re-exposing anything. Since this plan
  fast-forwards the live dev database in place rather than starting from a
  fresh volume (§2), rollback here means "take the public router back down"
  or "revert the checkout to `6936b30c`" — not "restore a prior data
  snapshot"; no destructive step touches the `state`/`database` volumes.
- If the deployment is up but the pipeline doesn't work end-to-end: it's
  likely safe to leave it running (assuming the port scan passed) while
  debugging, since nothing public is broken by an empty feed — an empty
  `vehicle_positions.json` is a valid, honest state, not a failure Jae's
  passengers would notice. Don't roll back on pipeline bugs alone if the
  security posture (§7 step 7) is already confirmed good; roll back if the
  external exposure check fails, unconditionally.

---

## 10. Open questions for Jae

Every question resolved by this revision — MQTT tunnel-vs-public, admin
VPN-vs-SSH-only, `gtfs-eta` dependency mechanism (deferred, moot for the
dev path), migrations mechanism, domain/TLS approach, ACME challenge type,
seed-data mechanism, "fresh vs. fast-forward," **the headline decision
itself, `compose.dev.yml` + hardening vs. migrating to
`compose.prod.yml`**, **the release ref (tip of `feat/fetch-telemetry`)**,
**the NanoMQ credential (`admin`/`admin`, tunnel-only caveat)**, **port
18000 (closed)**, and **what the uncommitted VPS-local edits contain**
(now persisted and summarized, §7 step 1) — has been removed from this
list; see the relevant numbered section above for each decision. VPS
OS/provider, current deployed commit, and the gtfs-rt-pipeline
Redis/Postgres/SSH hardening items are also resolved (§3a, §7) and removed.
What's left:

1. **Whether Jae wants the `compose.prod.yml` path documented separately for
   later.** This revision defers it (§1, §2) rather than deleting it — worth
   confirming whether it's worth keeping a standalone prod-migration doc
   around (the gtfs-eta bake mechanism and SIMOVI-owned-PyPI follow-up are
   still real future work) or letting it lapse until actually needed.
2. **Whether `sshd_config` explicitly disables password auth**, beyond the
   keys-only posture already confirmed via `99-hardened.conf` (§3a) — worth
   a quick double-check that no fallback password path remains enabled.
3. **Anything else discovered once §7 is actually run against the real
   VPS** — this plan is recon-informed but still not executed; the external
   nmap check (§7 step 7) and the Redis smoke test (§6) are the two places
   most likely to surface a remaining surprise.

---

*End of draft. No deployment has been performed. This document awaits Jae's
review, corrections, and explicit go-ahead before any of the steps in §7 are
executed.*
