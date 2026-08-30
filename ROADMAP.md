# Vehicle Zero Trust — Core Concepts & Getting Started

Companion doc to [`README.md`](./README.md) (the product thesis). This is
the working, get-your-hands-dirty version: what the product actually is
in concrete engineering terms, and the sequence to start building it.

---

## Core Concepts

**1. OEM authorization is a signal, not a root of trust.**
Every modern theft vector — CAN injection, OBD key programming, relay
attacks — works by making the vehicle's own trust chain conclude
`KEY_VALID = TRUE`. The product exists to add a second, independent
decision-maker that never asks the vehicle's opinion.

**2. Three pillars, made concrete:**
- **Identity** — phone-based cryptographic challenge-response (secure
  element on both ends), a PIN keypad as the no-phone fallback, and UWB
  time-of-flight distance bounding once BLE-only proximity proves too
  weak against relay attacks.
- **Integrity** — secure boot + secure element (ATECC608B/SE050) so key
  material never lives in plain MCU flash, plus anti-tamper sensors
  (accelerometer, case-open switch, supervised wire loop) that turn
  "removing the box" into a logged event rather than a silent bypass.
- **Behavior** — a CAN listener building context (locked + owner-absent
  + unexpected activity + start attempt = high risk). Deferred past
  MVP-1; not required to prove the core claim.

**3. The enforcement mechanism is physical, not software.**
A monostable (spring-return) relay, wired **normally-open /
energize-to-permit**, in series with only the crank-enable circuit.
Default state — unpowered, disconnected, destroyed — is "cannot start."
This is the answer to "what happens when the thief cuts my wires," and
it's the single most load-bearing engineering decision in the product.
Never use a latching/bistable relay here — it can hold "closed" with no
power applied, defeating the whole guarantee.

**4. No dependency on connectivity for the core decision.**
Arm/disarm authorization must work standalone (BLE/UWB + local secure
element), unlike remote-immobilize telematics systems whose cellular
command channel is itself an attack surface. Connectivity is for
telemetry/forensics/fleet features later — never the trust boundary.

**5. Cross-vehicle scalability via a thin adapter.**
Identity engine, integrity engine, policy engine, and secure hardware
stay ~90% identical across makes; only "where do I splice into this
model's crank-enable circuit" is vehicle-specific. This is the platform
bet, and it's testable early — build it for two very different
platforms before assuming it generalizes.

**6. Differentiation.**
IGLA/Ghost solve CAN injection but stay at PIN-button-only identity.
needCode solves relay attacks via UWB but leans on deep OEM/BCM
integration. Cartrack/Tracker solve recovery, not prevention, over a
live network channel. Nobody combines independent crypto identity + UWB
distance bounding + a rigorously validated fail-secure hardware design +
connectivity-independent trust in one retrofit unit. That combination is
the white space.

---

## How to Start

**Step 0 — Narrow the scope on purpose.**
Pick one vehicle (your own replacement, or a salvage-title car bought
purely for R&D) and one attack vector to defeat first: CAN injection —
it's both the dominant real-world theft method for recent Corollas and
the one this architecture answers most cleanly. Don't design for every
OEM or every attack vector simultaneously; that's the "bespoke per
vehicle" failure mode that would kill the platform thesis.

**Step 1 — Research, ~1–2 weeks, no soldering yet.**
- Get the factory wiring diagram for the target model's
  starter-enable/immobilizer circuit (service manual subscription — All
  Data or Mitchell1 — or model-specific forums). Don't guess at wiring.
- Buy a salvage BCM + instrument cluster + harness from a junkyard/eBay
  to get real CAN traffic on a bench, no vehicle required.
- Order core parts: ESP32-S3 dev board, MCP2515 CAN module, ATECC608B
  breakout, an automotive relay module, LIS3DH accelerometer. Under
  $300 total. Add a DW3000 UWB breakout now if proving distance-bounding
  early rather than retrofitting it later.

**Step 2 — Phase 0 bench build, 2–4 weeks. This is the actual MVP.**
Build and record a demo of exactly one thing: a relay that only closes
after an independent BLE/phone challenge-response succeeds, wired
normally-open/fail-secure, verified against a fault-injection matrix
(cut power, cut signal wire, unplug connector — relay stays open every
time). This bench video is simultaneously the engineering proof and the
pitch asset.

**Step 3 — Phase 1, real vehicle, private property only.**
Move the bench-proven circuit into a salvage test vehicle. Spend most of
this phase on the fail-safe test matrix (power loss mid-crank,
brownout, app unreachable) before it goes near a daily driver.

**Step 4 — Keep a dated build log throughout.**
Whether or not this becomes a company, a dated record of what was built
and when is the cheapest protection for IP/priority claims later, and
it's what turns "an idea" into something pitchable to an insurer, an
installer network, or an investor.

**Standing caveat:** before this touches a daily-driver vehicle, get the
interlock wiring reviewed by someone with real automotive electrical
experience — a miswired fail-secure relay is a bigger risk than the
theft it's meant to stop.
