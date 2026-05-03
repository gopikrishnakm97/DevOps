> Personal reference covering CI/CD pipeline design, Kubernetes deployments, traffic management, and Istio internals from a network perspective. Written for 6+ year DevOps / Platform Engineering roles.

---

## Table of Contents

1. [HLD vs LLD — What Interviewers Expect](#1-hld-vs-lld--what-interviewers-expect)
2. [CI/CD Pipeline Design (HLD)](#2-cicd-pipeline-design-hld)
3. [Scalable Secure K8s Deployment Pipeline (HLD + LLD)](#3-scalable-secure-k8s-deployment-pipeline-hld--lld)
4. [Ingress vs Load Balancer vs Service Mesh](#4-ingress-vs-load-balancer-vs-service-mesh)
5. [Istio Sidecar — How It Intercepts Traffic](#5-istio-sidecar--how-it-intercepts-traffic)
6. [Istio — Network & Kernel Perspective](#6-istio--network--kernel-perspective)
7. [Interview Cheat Sheet](#7-interview-cheat-sheet)

---

## 1. HLD vs LLD — What Interviewers Expect

### High Level Design (HLD)

The HLD round tests **system thinking**. You are expected to:

- Ask clarifying questions *before* drawing anything — deployment frequency, number of services, SLA, compliance requirements
- Identify trade-offs, not just name tools
- Cover failure modes, blast radius, and cost

**Common HLD prompts for DevOps:**

| Topic | What they want to see |
|---|---|
| CI/CD pipeline | Multi-env, parallel stages, GitOps, rollback |
| Cloud architecture | Multi-cloud, HA, DR, RTO/RPO |
| Observability stack | Metrics, logs, traces — the three pillars |
| Container platform | K8s clusters, service mesh, autoscaling |
| Secrets management | Vault, KMS, rotation policy |

### Low Level Design (LLD)

The LLD round tests **implementation depth**. You are expected to:

- Write or whiteboard actual config (Helm chart, Terraform module, GitHub Actions YAML)
- Justify every choice with a trade-off ("why Karpenter over Cluster Autoscaler?")
- Know the failure modes of the thing you are designing

**Common LLD prompts:**

- Write a Helm chart for a stateful service with HPA and PodDisruptionBudget
- Design a Terraform module layout for 5 teams
- Design a Prometheus alerting rule using error budget burn rate
- Walk me through exactly what happens when a pod is deleted during a rolling update

### Key mindset shift at 6+ years

At this level, "we used Datadog" is not an answer. The interviewer wants:

> "We set SLOs on p99 latency and error rate. The burn rate alert fires when we are consuming the monthly error budget 14× faster than normal, which gives us about 1 hour to act before breaching SLO. We chose that threshold to avoid alert fatigue from transient spikes."

---

## 2. CI/CD Pipeline Design (HLD)

### The pipeline flow

```
Git push / PR merge
       │
       ▼
  CI build ──────────────────────────────────────────────────┐
  (compile, unit test, lint — all parallel)                  │
       │                                                      │
       ▼                                                      ▼
  Security gate                                         SAST / secret scan
  (runs concurrently)                                   (fail fast, cheap)
       │
       ▼
  Artifact registry  ←── OCI image, signed with Cosign, tagged with git SHA
       │
       ▼
  GitOps config repo  ←── PR to bump image tag
       │
       ├──▶  Dev / preview  (auto-deploy on merge)
       │
       ├──▶  Staging  (integration tests, load tests)
       │
       ▼
  Approval gate  (manual or policy-based)
       │
       ▼
  Production  (canary 5% → 100% via Argo Rollouts)
       │
       ▼
  Post-deploy SLO smoke test  ──(fail)──▶  Auto-rollback via git revert
```

### Platform components

```
Control plane
├── Orchestrator        (GitHub Actions, Jenkins, Tekton)
├── Policy engine       (OPA, Kyverno)
└── Secrets manager     (Vault, AWS Secrets Manager)

Execution layer
├── Ephemeral runners   (K8s pods, AWS Fargate — never shared VMs)
├── Build cache         (layer cache, dep cache, artifact cache)
└── Artifact store      (ECR, GCR, Nexus)

Target environments
├── Dev / preview       (ephemeral, per-PR)
├── Staging             (persistent, prod-like)
├── Production          (canary / blue-green)
└── DR                  (failover target)
```

### The 5 dimensions to always cover in an HLD answer

**1. Speed vs safety**
Design for parallelism (lint, unit tests, SAST all concurrent) but keep hard sequential gates before environment promotion. Target: p95 CI time under 5 minutes → requires aggressive caching and ephemeral K8s runners, not shared VMs.

**2. Blast radius control**
Progressive delivery. Never deploy to 100% of production at once. Canary starts at 1–5%, automated SLO checks run for X minutes, then auto-promote or auto-rollback.

**3. Artifact immutability**
One build, many deploys. Same container image that passes staging must be what lands in production — never rebuild for prod. Tag with git SHA. Sign with Cosign.

**4. Security shift-left**
- SAST and secret scanning: CI stage (fail fast)
- DAST and container image scanning: post-build
- SBOM + provenance attestation: generated at build time
- Admission policy (Kyverno): cluster refuses unsigned images

**5. Observability of the pipeline itself**
- Alert when build failure rate > 20%
- Alert when p95 CI duration increases > 50% week-over-week
- Tools: Datadog CI Visibility, OpenTelemetry traces on pipeline steps

### Key trade-offs to prepare for

| Question | Answer |
|---|---|
| Push vs pull deployment? | Pull (ArgoCD/Flux) — CI never gets cluster credentials, fully auditable |
| Monorepo vs polyrepo CI? | Monorepo needs change detection (build only affected services); polyrepo simpler per-service |
| Skip staging gate? | Almost never for stateful services; for stateless + high coverage, a feature flag can substitute |
| Shared vs dedicated runners? | Dedicated ephemeral (K8s pods) — no cross-job secret leakage, clean environment every run |

### Strong closing statement

> "The goal of the CI/CD platform is to make the right thing — tested, secure, observable deployments — easier than the wrong thing, and to make failures loud and cheap rather than silent and expensive."

---

## 3. Scalable Secure K8s Deployment Pipeline (HLD + LLD)

### Full architecture layers

```
Internet
    │
    ▼
Cloud Load Balancer  (L4 — one public IP)
    │
    ▼
Ingress Controller  (L7 — TLS, host/path routing, rate limiting)
    │
    ▼
Kubernetes cluster
├── Workloads          (Deployment, StatefulSet)
├── HPA / KEDA         (pod autoscaling)
├── Karpenter          (node autoscaling)
├── PDB                (disruption budget)
├── Network policies   (Cilium, zero-trust)
├── RBAC               (namespace-scoped)
└── Secrets (ESO)      (External Secrets Operator → Vault)
    │
    ▼
Observability
├── SLO dashboard      (error budget, burn rate)
├── Distributed tracing (OTEL, Jaeger, Tempo)
└── Metrics + alerts   (Prometheus, Grafana)
```

### Zero-downtime deployment — 5 things that must work together

#### 1. Rolling update strategy

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 25%        # spin up new pods before killing old ones
    maxUnavailable: 0    # never reduce capacity during rollout
```

`maxUnavailable: 0` is the key. Without it, K8s can terminate old pods before new ones pass readiness — that gap is your downtime.

#### 2. Readiness probe that actually reflects readiness

```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 3
```

The `/ready` endpoint must check all downstream dependencies (DB connection, cache, feature flags). An endpoint that only checks "is HTTP server up" causes premature traffic routing.

#### 3. PodDisruptionBudget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: svc-pdb
spec:
  minAvailable: "75%"
  selector:
    matchLabels:
      app: my-service
```

Blocks node drains, cluster upgrades, and Karpenter scale-downs from killing too many pods simultaneously.

#### 4. Graceful shutdown with preStop hook

```yaml
lifecycle:
  preStop:
    exec:
      command: ["sleep", "5"]
terminationGracePeriodSeconds: 30
```

K8s removes the pod from service endpoints and sends SIGTERM at roughly the same time. The 5-second sleep gives the load balancer time to stop routing new connections before the process begins shutting down.

#### 5. Canary via Argo Rollouts + Istio

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
spec:
  strategy:
    canary:
      steps:
        - setWeight: 5      # send 5% traffic to new version
        - pause: {duration: 10m}
        - setWeight: 50
        - pause: {duration: 5m}
      analysis:
        templates:
          - templateName: slo-check  # auto-rollback if SLO breached
```

### Scaling architecture

#### Pod-level: HPA vs KEDA

| Scenario | Tool |
|---|---|
| CPU/memory driven load | HPA |
| Queue depth, Kafka lag, cron burst | KEDA |
| Scale to zero (non-critical services) | KEDA |

#### Node-level: Karpenter

```yaml
apiVersion: karpenter.sh/v1alpha5
kind: NodePool
spec:
  template:
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand", "spot"]
      limits:
        cpu: 1000
```

Karpenter provisions the right instance type automatically in ~60 seconds. Use on-demand for stateful workloads, spot for stateless burst capacity.

#### Pre-scaling for known events

Reactive autoscaling always has a lag (cold start, JVM warmup, cache misses). For predictable traffic spikes (sales, launches), pre-warm with a manual HPA override or a CronJob that scales up in advance.

### Security controls summary

| Layer | Control | Why |
|---|---|---|
| Pipeline | Cosign image signing + Kyverno admission | Cluster rejects unsigned images |
| Pipeline | Trivy scan in CI | Block critical CVEs before registry |
| Ingress | TLS termination + rate limiting | Prevent abuse before it hits pods |
| Inter-service | Istio mTLS STRICT mode | No plaintext inside the cluster |
| Identity | Workload Identity (IRSA / WIF) | No static credentials in env vars |
| Secrets | External Secrets Operator → Vault | Secrets fetched at runtime |
| RBAC | Namespace-scoped roles | No cluster-admin for app accounts |
| Network | Cilium network policies (default-deny) | Pods only talk to allowlisted destinations |
| Runtime | Falco | Detects unexpected syscalls |

### Strong closing statement

> "The design's goal is that a bad deploy is automatically detected and reversed in under 2 minutes, a traffic spike is absorbed without dropping a single request, and no human ever needs kubectl access to production for routine operations."

---

## 4. Ingress vs Load Balancer vs Service Mesh

### Mental model — they are complementary layers, not alternatives

```
Internet
    │
    ▼
Cloud Load Balancer   (L4 — TCP/UDP — north-south — one per Service)
    │
    ▼
Ingress Controller    (L7 — HTTP — north-south — one shared entry point)
    │
    ▼
ClusterIP Service     (internal discovery, kube-proxy)
    │
    ▼
Service Mesh sidecar  (L7 — east-west — pod-to-pod)
    │
    ▼
Pod
```

### Load Balancer (type: LoadBalancer)

- **OSI layer:** L4 (TCP/UDP)
- **Direction:** North-south only
- **Scope:** One cloud NLB/ALB per Service
- **Cost model:** One public IP per Service exposed — expensive at scale
- **Awareness:** No HTTP awareness — cannot route by path or hostname
- **Use when:** Non-HTTP workloads (databases, game servers, MQTT, DNS). For HTTP, almost always prefer Ingress.

### Ingress

- **OSI layer:** L7 (HTTP/HTTPS)
- **Direction:** North-south only
- **Scope:** One shared entry point for many Services
- **Cost model:** One public IP shared across all HTTP Services
- **Awareness:** Full HTTP — host/path routing, TLS termination, rate limiting, JWT auth
- **Implementations:** NGINX Ingress Controller, Traefik, AWS ALB Ingress Controller, Kong
- **Limits:** Only handles external traffic. No control over pod-to-pod (east-west) communication.
- **Future:** Gateway API is the modern successor — more expressive, role-based (infrastructure team owns Gateway, app team owns HTTPRoute)

```yaml
# Example: path-based routing
rules:
  - host: api.example.com
    http:
      paths:
        - path: /users
          backend:
            service: { name: user-svc, port: 80 }
        - path: /orders
          backend:
            service: { name: order-svc, port: 80 }
```

### Service Mesh (Istio, Linkerd, Cilium Service Mesh)

- **OSI layer:** L7 (HTTP/gRPC)
- **Direction:** East-west (pod-to-pod inside the cluster)
- **Scope:** Every service-to-service call
- **Cost model:** ~50MB memory + ~5ms latency overhead per pod (sidecar); eBPF-based meshes avoid this
- **What it unlocks:**
  - mTLS between every pod pair — zero-trust inside the cluster
  - Retries, circuit breaking, timeout — in config, not code
  - Traffic splitting for canary without app changes
  - Distributed tracing with zero instrumentation
  - Golden-signal metrics for every service pair

### Quick comparison table

| Dimension | Load Balancer | Ingress | Service Mesh |
|---|---|---|---|
| OSI layer | L4 | L7 | L7 |
| Traffic direction | North-south | North-south | East-west |
| Cost model | 1 IP per Service | 1 IP for many | CPU per pod |
| HTTP awareness | No | Yes | Yes |
| mTLS | No | Partial (TLS termination) | Full mutual TLS |
| Canary routing | No | Limited | Yes |
| Observability | Basic | Basic | Full traces + metrics |
| Complexity | Low | Medium | High |

### When to skip the service mesh

For clusters with fewer than ~20 services, the operational overhead of Istio (complex CRDs, control plane management, debug difficulty) outweighs the benefit. Start with Ingress + Cilium network policies. Add a mesh when:

- Compliance requires mTLS between internal services
- You need traffic splitting without code changes
- You want automatic pod-to-pod observability

### Trade-off question: LoadBalancer Service directly vs Ingress?

Use LoadBalancer directly for non-HTTP workloads, or when a service needs its own dedicated IP for security/isolation (e.g., a bastion or an admin API that must never share infrastructure with public traffic).

---

## 5. Istio Sidecar — How It Intercepts Traffic

### Step 1: Injection (MutatingWebhookConfiguration)

When a pod is created in a namespace labelled `istio-injection=enabled`, the Kubernetes API server calls istiod's MutatingWebhookConfiguration endpoint before the pod starts.

istiod patches two extra containers into the pod spec:

```
Pod spec after injection
├── istio-init     (init container — runs as root, writes iptables rules, then exits)
├── istio-proxy    (Envoy sidecar — runs for the pod's lifetime, UID 1337)
└── your-app       (unmodified — no code change required)
```

### Step 2: iptables rules (written by istio-init)

`istio-init` runs first, writes these rules into the pod's network namespace, then exits:

```
OUTBOUND rules (OUTPUT chain → ISTIO_OUTPUT):
  - Traffic from UID 1337 (Envoy itself) → RETURN  ← loop prevention
  - Traffic to localhost → RETURN
  - Everything else → REDIRECT to :15001  ← Envoy outbound listener

INBOUND rules (PREROUTING chain → ISTIO_INBOUND):
  - Traffic to :15090 (Envoy metrics) → RETURN
  - Everything else → REDIRECT to :15006  ← Envoy inbound listener
```

After `istio-init` exits, these rules are permanent in the pod netns. Envoy owns every socket.

### Step 3: Outbound capture

```
app calls connect(svc-b:80)
         │
         ▼
iptables OUTPUT hook → ISTIO_OUTPUT rule matches
         │
         ▼  REDIRECT
127.0.0.1:15001  (Envoy outbound listener)
         │
         ▼
Envoy reads SO_ORIGINAL_DST  → recovers real destination svc-b:80
Envoy consults xDS route table → finds upstream cluster
Envoy applies VirtualService / DestinationRule policies
Envoy opens mTLS connection to peer Envoy
```

**Key detail:** `SO_ORIGINAL_DST` is a Linux kernel socket option. When iptables rewrites the destination (NAT), it stores the original address in the socket. Envoy reads it with `getsockopt(fd, SOL_IP, SO_ORIGINAL_DST)` to know where to actually send the traffic.

### Step 4: mTLS handshake (Envoy ↔ Envoy)

Both sides use SPIFFE/X.509 certificates issued by istiod's built-in CA:

```
Pod A Envoy cert:  spiffe://cluster.local/ns/default/sa/svc-a
Pod B Envoy cert:  spiffe://cluster.local/ns/default/sa/svc-b
```

Both sides present their cert and verify the peer's cert — mutual TLS. `AuthorizationPolicy` rules then enforce which SPIFFE identities are allowed to call which services. This is zero-trust inside the cluster.

```yaml
# Example: only allow svc-a to call svc-b
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: svc-b-policy
spec:
  selector:
    matchLabels:
      app: svc-b
  rules:
    - from:
        - source:
            principals: ["cluster.local/ns/default/sa/svc-a"]
```

### Step 5: Inbound capture (at the destination pod)

```
mTLS packet arrives at pod B eth0
         │
         ▼
iptables PREROUTING → ISTIO_INBOUND rule matches
         │
         ▼  REDIRECT
:15006  (Envoy inbound listener)
         │
Envoy terminates TLS
Envoy verifies peer SPIFFE cert
Envoy checks AuthorizationPolicy
Envoy emits trace span + golden-signal metrics
         │
         ▼
127.0.0.1:80  (app-b on loopback — receives plaintext)
```

The app sees a normal HTTP connection from localhost. It has no knowledge of mTLS, retries, or observability happening around it.

### The infinite loop — and why it does not happen

Without the UID 1337 exemption, Envoy's own forwarded packets would hit the ISTIO_OUTPUT rule and be redirected back to :15001 — an infinite loop.

The exemption: `iptables -t nat -A ISTIO_OUTPUT -m owner --uid-owner 1337 -j RETURN`

Envoy runs as UID 1337. Its egress traffic matches this rule first and bypasses the redirect entirely.

### What Envoy does beyond just forwarding

Every request through a sidecar pair gives you:

| Feature | Mechanism |
|---|---|
| Retries | DestinationRule `connectionPool` + `outlierDetection` |
| Circuit breaking | DestinationRule `outlierDetection` |
| Timeout | VirtualService `timeout` |
| Traffic splitting | VirtualService `weight` |
| Fault injection | VirtualService `fault` (for chaos testing) |
| Distributed trace | Injects/reads `x-b3-traceid` headers |
| Metrics | Emits request count, duration, response code per service pair |

---

## 6. Istio — Network & Kernel Perspective

### The pod network namespace

Every Kubernetes pod has its own **Linux network namespace** — an isolated instance of the kernel's network stack. It has:

- Its own routing table
- Its own iptables rules
- Its own `lo` (loopback) and `eth0` (veth peer) interfaces

All containers in a pod share this single netns. This is why:
- Containers reach each other on `localhost`
- Envoy (separate process) intercepts all app traffic without touching app code
- `istio-init` (writing iptables rules) and `istio-proxy` (Envoy) work from the same network context

### The two interfaces inside the pod

**`lo` (loopback, 127.0.0.1)**
Used by the iptables REDIRECT mechanism. When a REDIRECT rule fires, the kernel rewrites the destination to `127.0.0.1` and the packet loops back within the pod netns to Envoy's listener port. This is in-kernel — no physical NIC involved, sub-microsecond.

**`eth0` (veth pair)**
One end of a virtual ethernet cable inside the pod netns, the other end attached to a Linux bridge (`cbr0` or `cni0`) on the node. Every packet that leaves the pod crosses this veth pair.

### Packet path — outbound, step by step

```
1. app calls connect(10.96.0.1:80)          ← Cluster IP of svc-b
2. Kernel routes packet → OUTPUT netfilter hook
3. iptables ISTIO_OUTPUT rule fires → REDIRECT to 127.0.0.1:15001
4. Packet delivered to Envoy on lo:15001
5. Envoy: getsockopt(SO_ORIGINAL_DST) → 10.96.0.1:80
6. Envoy: DNS/xDS lookup → real pod IP 10.244.2.8:80
7. Envoy opens TCP to 10.244.2.8:80 (as UID 1337)
8. iptables OUTPUT → UID 1337 → RETURN (exempt)
9. Packet leaves pod via eth0 → veth peer on node → bridge
10. If cross-node: CNI overlay → other node → bridge → pod B veth → eth0
11. Pod B: PREROUTING → REDIRECT :15006 → pod B Envoy
12. Pod B Envoy: terminates TLS, forwards to 127.0.0.1:80 (app-b)
```

### Node-level topology

```
Node 1 (10.0.0.1)
├── Pod A (10.244.1.5)
│   ├── app-a
│   ├── Envoy (UID 1337)
│   └── eth0 ──veth──┐
│                     │
└── cbr0 (Linux bridge)──────── ens0 (node NIC)
                                        │
                              ┌─────────┴──────────┐
                         VXLAN / BGP / eBPF overlay network
                                        │
Node 2 (10.0.0.2)                       │
└── cbr0 ──────────────────────── ens0 ─┘
    └── Pod B (10.244.2.8)
        ├── Envoy (UID 1337)
        └── app-b
```

**Same-node traffic:** Pod A veth → bridge → Pod B veth. Entirely in-kernel, no physical NIC. Sub-millisecond latency.

**Cross-node traffic:** Depends on CNI plugin.

### CNI plugins — cross-node routing comparison

| CNI | Mechanism | Encapsulation | Performance |
|---|---|---|---|
| Flannel | VXLAN | UDP wraps IP packets | Moderate — extra encap overhead |
| Calico | BGP | None — native IP routing | High — no encapsulation |
| Cilium | eBPF | None (host routing mode) | Highest — bypasses iptables entirely |
| AWS VPC CNI | VPC native routing | None | High — pods get real VPC IPs |

### iptables chains — exact rules Istio writes

```
# Outbound chain (nat table)
-N ISTIO_OUTPUT
-A OUTPUT -t nat -p tcp -j ISTIO_OUTPUT

# Rules inside ISTIO_OUTPUT (evaluated top-to-bottom):
-A ISTIO_OUTPUT -m owner --uid-owner 1337 -j RETURN         # Envoy itself → skip
-A ISTIO_OUTPUT -d 127.0.0.1/32 -j RETURN                   # localhost → skip
-A ISTIO_OUTPUT -j REDIRECT --to-ports 15001                 # everything else → Envoy

# Inbound chain (nat table)
-N ISTIO_INBOUND
-A PREROUTING -t nat -p tcp -j ISTIO_INBOUND

# Rules inside ISTIO_INBOUND:
-A ISTIO_INBOUND -p tcp --dport 15090 -j RETURN             # Envoy metrics → skip
-A ISTIO_INBOUND -p tcp --dport 15021 -j RETURN             # Envoy health → skip
-A ISTIO_INBOUND -j REDIRECT --to-ports 15006               # everything else → Envoy
```

### Envoy ports reference

| Port | Purpose |
|---|---|
| 15001 | Outbound listener (captures all egress) |
| 15006 | Inbound listener (captures all ingress) |
| 15021 | Health check endpoint |
| 15090 | Prometheus metrics (exempt from redirect) |
| 15000 | Admin API (local only) |

### SO_ORIGINAL_DST — the kernel trick that makes it work

When iptables performs a REDIRECT (a form of DNAT — Destination NAT), it stores the original destination address in the socket's connection tracking entry.

Envoy reads it:
```c
struct sockaddr_in orig_dst;
socklen_t len = sizeof(orig_dst);
getsockopt(fd, SOL_IP, SO_ORIGINAL_DST, &orig_dst, &len);
// orig_dst now contains the original svc-b:80 the app intended
```

Without this, Envoy would only see the redirected address (127.0.0.1:15001) and have no idea where to forward the connection.

### Cilium eBPF — why it is faster

The entire iptables/loopback/redirect chain has overhead:
- Each packet traverses multiple netfilter hooks
- iptables rules evaluated linearly — O(n) per packet in a busy cluster
- Extra loopback round-trip adds latency

Cilium attaches **eBPF programs directly to TC (traffic control) hooks** on the veth interfaces:

```
Packet arrives at veth → eBPF program runs in kernel context → inspect, allow/deny, redirect
                         (No loopback, no netfilter, no iptables evaluation)
```

Result:
- ~30–50% lower p99 latency vs iptables-based sidecars at high packet rates
- No sidecar memory overhead per pod
- Same security guarantees (identity-based policy, encryption)

**Interview one-liner:**
> "Istio intercepts at the socket layer via iptables NAT and loopback redirect. Cilium intercepts at the packet layer via eBPF on the veth — lower overhead, same security guarantees. The trade-off is Cilium requires a newer kernel (≥5.10) and different operational expertise."

---

## 7. Interview Cheat Sheet

### Questions that catch senior candidates off-guard

| Question | What they want |
|---|---|
| How does Envoy avoid an infinite redirect loop? | UID 1337 exempt in iptables `--uid-owner` rule |
| How does Envoy know the real destination after redirect? | `getsockopt(SO_ORIGINAL_DST)` syscall |
| What happens to in-flight requests during a rolling update? | `preStop` sleep + `terminationGracePeriodSeconds` drain window |
| What prevents cluster autoscaler from breaking your PDB? | PDB `minAvailable` — node drain is blocked if it would violate PDB |
| Push vs pull CD model? | Pull (ArgoCD) — CI has no cluster access, auditable, drift-detectable |
| Why Karpenter over Cluster Autoscaler? | Right-sizes instances per workload, faster provisioning (~60s), consolidation |
| When NOT to use a service mesh? | < 20 services, no mTLS compliance requirement, team lacks Istio expertise |

### Failure modes to always mention

- **Missing `maxUnavailable: 0`** → pods terminated before replacements are ready → downtime during rollout
- **Readiness probe too shallow** → routes traffic to pods that aren't actually ready → elevated errors
- **No PDB** → node drain during upgrade kills too many replicas simultaneously
- **No `preStop` hook** → in-flight requests dropped when SIGTERM arrives during load balancer draining
- **iptables UID exemption absent** → Envoy enters infinite redirect loop → pod networking broken
- **Artifact rebuilt for production** → "works in staging" class of bugs — environment-specific differences creep in

### Useful numbers to know

| Metric | Typical value |
|---|---|
| Karpenter node provision time | ~60 seconds |
| Envoy sidecar memory overhead | ~50 MB per pod |
| Envoy added latency (p99) | < 5 ms at normal load |
| HPA scale-up lag | 15–30 seconds (default stabilization window) |
| KEDA polling interval | configurable, default 30 seconds |
| iptables REDIRECT overhead | < 0.1 ms per packet |
| eBPF vs iptables latency improvement | 30–50% at high packet rates |

---

*Last updated: 2026. Covers Istio 1.x, Kubernetes 1.28+, Karpenter v0.3x, Cilium 1.15+.*
