# Vehicle Zero Trust

**An endpoint security platform for existing vehicles**

> Early product thesis — not a finished solution. The goal here is to make
> the problem, the insight, the proposed architecture, and the unanswered
> questions very clear.

## One-line pitch

Vehicle Zero Trust is an aftermarket endpoint-security platform that gives
existing vehicles an independent, hardware-backed trust layer — making
compromise of the vehicle's OEM security insufficient to authorize its use.

---

## The Problem

Modern cars are computers on wheels, but their security model still relies
heavily on the vehicle's own systems:

```
Key → Immobilizer → Vehicle network → ECU → Start
```

Modern vehicle theft increasingly attacks that digital trust chain.

If an attacker successfully bypasses or manipulates the OEM authorization
mechanism, the vehicle may ultimately believe:

```
KEY_VALID        = TRUE
START_AUTHORIZED = TRUE
```

At that point, many existing protections have already lost.

The fundamental problem is:

> The same environment we're trying to protect is also responsible for
> deciding whether the driver is trusted.

---

## The Idea

Create an independent aftermarket security endpoint that can be installed
in vehicles already on the road.

Think: **EDR + hardware root of trust + Zero Trust identity for vehicles.**

The security endpoint operates independently of the OEM's authentication
decision.

```
                    DRIVER
                       │
                Authentication
                       ↓
             ┌───────────────────┐
             │ VEHICLE SECURITY  │
             │     ENDPOINT      │
             │                   │
             │ Identity          │
             │ Integrity         │
             │ Anti-Tamper       │
             │ Runtime Detection │
             │ Policy Engine     │
             └─────────┬─────────┘
                       │
                 Authorization
                       │
                       ↓
                    VEHICLE
```

The core principle:

> OEM authorization is a signal — not a root of trust.

Even if the car says:

```
OEM_KEY_VALID = TRUE
```

our endpoint can independently determine:

```
OWNER_AUTHENTICATED  = FALSE
ENDPOINT_INTEGRITY   = TRUE
DRIVE_AUTHORIZED     = FALSE
```

---

## Three Security Pillars

### 1. Identity — Who is driving?

Independent authentication of the legitimate user.

Potential mechanisms: phone cryptographic identity, hardware token, PIN,
NFC/UWB, or combinations of them.

The important distinction is that we're not relying solely on the OEM key.

### 2. Integrity — Is the security environment trustworthy?

The endpoint protects itself.

Potential capabilities:

- Secure Boot
- Secure Element
- Device Identity
- Signed Firmware
- Anti-Rollback
- Power Tamper Detection
- Physical Tamper Detection
- Hardware Binding
- Authenticated Event Log

Removing, replacing, or resetting the security module should itself
become a security event rather than simply disabling the protection.

### 3. Behavior — Does what's happening make sense?

The endpoint observes vehicle state and builds an independent security
context.

For example:

```
Vehicle locked
+
Owner absent
+
Unexpected electronic activity
+
Start attempt
----------------
HIGH RISK
```

Initially this can be deterministic rules. Eventually it could become a
vehicle EDR detection engine.

---

## The Long-Term Platform

This shouldn't become "a better immobilizer." The larger vision is:
**Endpoint Security for Vehicles.**

```
                    CLOUD XDR
                       ▲
                       │
               Threat Intelligence
                       │
              ┌────────┴────────┐
              │ Vehicle Endpoint│
              │                 │
              │ Identity        │
              │ Integrity       │
              │ Runtime EDR     │
              │ Anti-Tamper     │
              │ Policy          │
              │ Forensics       │
              └────────┬────────┘
                       │
                Vehicle Adapter
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
      Toyota         Hyundai          VW
```

Ideally, perhaps 80–90% of the security platform is identical, while a
thin vehicle abstraction layer handles OEM/model differences.

That is what could turn it from an aftermarket anti-theft device into a
security platform.

---

## Why Isn't Existing Anti-Theft Enough?

There are already good solutions:

- Immobilizers such as **IGLA** provide additional authorization.
- Companies such as **PlaxidityX** provide sophisticated vehicle
  intrusion/theft detection and prevention.
- Companies such as **Upstream** provide cloud XDR across millions of
  vehicles.

So the thesis is **not**: "Nobody protects cars."

The potential gap is:

> A universal, independent, hardware-backed Zero Trust endpoint that can
> be retrofitted into vehicles already on the road.

Instead of only asking "Is this CAN traffic malicious?" we ask "Why
should we trust this vehicle's authorization decision at all?"

---

## Why This Could Become Bigger Than Theft Prevention

The first use case is extremely understandable: compromising the OEM
security should not be enough to steal the car.

But once an endpoint exists inside millions of vehicles, the platform
potentially expands into:

```
Anti-theft
     ↓
Vehicle EDR
     ↓
Tamper detection
     ↓
Vehicle identity
     ↓
Remote attestation
     ↓
Forensics
     ↓
Fleet security
     ↓
Insurance risk reduction
     ↓
Vehicle XDR
```

Potential customers therefore aren't necessarily only consumers. They
could eventually include:

```
Consumers → insurers → fleets → leasing companies → security providers → OEMs
```

---

## The Critical Questions

These are the questions to put directly into the presentation, because
we don't yet know whether this is a great startup or simply another
immobilizer.

**Technical feasibility** — Can we establish a truly independent trust
boundary without trusting compromised OEM components? What must we
actually control to prevent unauthorized driving? Can that enforcement
mechanism remain safe under every failure condition?

**Universality** — Can one hardware platform support Toyota, Hyundai,
Kia, VW, etc.? How much vehicle-specific engineering is required? If
every model requires deep reverse engineering, the platform thesis
becomes much weaker.

**Anti-tamper** — What happens when the attacker knows our product
exists? Can they locate, remove, replace, bypass, or emulate it? Can we
design installation so bypassing the endpoint is materially harder than
defeating the original vehicle security?

**Identity** — What authentication gives strong security without making
driving annoying? Phone proximity alone probably isn't sufficient. What
happens when the owner's phone is dead, stolen, or replaced?

**Safety** — How do we guarantee that the security system can never
disable a moving vehicle? How do we fail safely when hardware/software
malfunction?

**Attack surface** — Are we introducing a new vulnerability ourselves?
BLE, cellular connectivity, firmware updates, installer tools, and cloud
commands all become potential attack surfaces.

**Detection** — What vehicle signals can we trust? Can we distinguish
theft from legitimate repair, towing, battery replacement, servicing,
and unusual owner behavior without excessive false positives?

**Installation** — Can a certified installer put this into a vehicle in
30–60 minutes? Can installation avoid permanent modifications and
warranty problems?

**Economics** — Can we manufacture and install it cheaply enough? Would
consumers pay $200, $500, or $1,000? More importantly, would an insurer
subsidize it if it demonstrably reduces theft claims?

**Competition** — Why are we meaningfully better than IGLA, Ghost,
PlaxidityX/vDome, and other existing solutions? Is our moat technology,
hardware architecture, cross-OEM abstraction, threat intelligence,
distribution — or some combination?

---

## The First Hypothesis to Prove

> Can we build a universal retrofit trust anchor for vehicles?

One endpoint. Two very different vehicle architectures. Same:

- Identity Engine
- Integrity Engine
- Policy Engine
- Secure Hardware
- Authentication
- Telemetry
- Cloud

Different only in: **Vehicle Adaptation Layer**.

If we can protect a Toyota and a fundamentally different vehicle
platform using the same endpoint with only a thin adapter, we have early
evidence that we're building a platform.

If every vehicle requires a completely bespoke security system, we learn
early that the thesis needs to change.
