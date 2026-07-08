# Production Microservices Platform — End-to-End Guide

5 microservices → Docker → Kubernetes → NGINX Ingress (path routing) →
Blue-Green & Canary deployments → custom domain `ganga888.online` → free SSL.

This mirrors what real teams run in production. Swap the sample Flask apps
for your real services later — the pipeline (build → deploy → route →
release strategy → TLS) stays identical.

```
microapp/
├── service1..5/          # Flask app + Dockerfile + requirements.txt each
└── k8s/
    ├── base/              # namespace + 5 deployments + 5 services
    ├── ingress/           # path-based routing (/service1, /service2, ...)
    ├── cert-manager/       # Let's Encrypt ClusterIssuers
    ├── blue-green/         # blue-green example (service1)
    └── canary/             # canary example (service2)
```

---

## 1. Build & push Docker images

For each service (repeat for service1 → service5):

```bash
cd service1
docker build -t YOUR_DOCKERHUB_USERNAME/service1:v1 .
docker push YOUR_DOCKERHUB_USERNAME/service1:v1
```

Test locally before pushing:
```bash
docker run -p 5000:5000 YOUR_DOCKERHUB_USERNAME/service1:v1
curl localhost:5000/          # {"service":"service1","version":"v1",...}
curl localhost:5000/healthz
```

**Why this Dockerfile is production-shaped:** multi-stage build (small final
image, no build tooling shipped), runs as a non-root user, has a
`HEALTHCHECK`, and uses `gunicorn` instead of Flask's dev server.

Replace `YOUR_DOCKERHUB_USERNAME` in every manifest under `k8s/` with your
real registry path (Docker Hub, ECR, ACR, GCR — same idea everywhere).

---

## 2 & 3. Deploy the 5 microservices (Deployment + Service each)

```bash
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/deployment-service1.yaml
kubectl apply -f k8s/base/deployment-service2.yaml
kubectl apply -f k8s/base/deployment-service3.yaml
kubectl apply -f k8s/base/deployment-service4.yaml
kubectl apply -f k8s/base/deployment-service5.yaml

kubectl get pods -n microapp
kubectl get svc -n microapp
```

Each file defines **one Deployment (2 replicas) + one ClusterIP Service**,
with readiness/liveness probes wired to `/readyz` and `/healthz`. Services
are `ClusterIP` — not exposed directly; the Ingress in the next step is the
single entry point, which is the standard production pattern.

---

## 4. NGINX Ingress Controller — path-based routing (`/service1`, `/service2`, ...)

Install the controller (Helm is the standard way):
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace
```

Get its external IP (this is what your DNS `A` record will point to):
```bash
kubectl get svc -n ingress-nginx ingress-nginx-controller
```

Apply the routing rules:
```bash
kubectl apply -f k8s/ingress/ingress.yaml
```

This single Ingress routes:
- `ganga888.online/service1` → `service1`
- `ganga888.online/service2` → `service2`
- ... through `service5`

using regex capture groups + `rewrite-target` so each backend still sees
its own root path (`/`) rather than `/service1/`.

Test with curl once DNS is live:
```bash
curl https://ganga888.online/service1/
curl https://ganga888.online/service2/
```

---

## 6. DNS — point `ganga888.online` at your cluster

At your domain registrar (wherever `ganga888.online` is registered):
- Create an **A record**: `@` (or `ganga888.online`) → the external IP from
  `kubectl get svc -n ingress-nginx ingress-nginx-controller`
- If your ingress controller's LoadBalancer gives a hostname instead of an
  IP (common on AWS ELB), create a **CNAME** to that hostname instead.

DNS propagation can take a few minutes to a few hours. Verify with:
```bash
dig ganga888.online +short
```

---

## 7. Free SSL certificates (cert-manager + Let's Encrypt)

Install cert-manager:
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl get pods -n cert-manager   # wait until all 3 pods are Running
```

Edit `k8s/cert-manager/cluster-issuer.yaml` — set your real email — then:
```bash
kubectl apply -f k8s/cert-manager/cluster-issuer.yaml
```

The Ingress (`k8s/ingress/ingress.yaml`) already has:
```yaml
cert-manager.io/cluster-issuer: "letsencrypt-prod"
tls:
  - hosts: [ganga888.online]
    secretName: ganga888-tls
```
Once DNS resolves and the Ingress is applied, cert-manager automatically
completes an HTTP-01 challenge and issues the cert. Check progress:
```bash
kubectl get certificate -n microapp
kubectl describe certificate ganga888-tls -n microapp
```
**Tip:** test with `letsencrypt-staging` first — Let's Encrypt's real
issuer rate-limits aggressively, and staging certs (untrusted by browsers,
but functionally identical) let you validate the whole flow for free before
switching the annotation to `letsencrypt-prod`.

---

## 5. Blue-Green deployment (example: service1)

```bash
kubectl apply -f k8s/blue-green/service1-blue-green.yaml
```

This creates **two full Deployments** (`service1-blue` running v1,
`service1-green` running v2) and **one Service** whose `selector` decides
which one is live. Cutover is a single selector patch — no rebuild, no pod
churn on the live side:

```bash
# Cut traffic over to green (v2):
kubectl patch svc service1 -n microapp \
  -p '{"spec":{"selector":{"app":"service1","slot":"green"}}}'

# Instant rollback if something's wrong:
kubectl patch svc service1 -n microapp \
  -p '{"spec":{"selector":{"app":"service1","slot":"blue"}}}'
```

This is the classic "zero-downtime, instant-rollback" release strategy —
you're trading double the resource footprint (both versions run
simultaneously) for a release that's essentially risk-free to reverse.

---

## Canary deployment (example: service2)

```bash
kubectl apply -f k8s/canary/service2-canary.yaml
```

Unlike blue-green (all-or-nothing), canary sends a **percentage** of live
traffic to the new version while the rest keeps hitting stable v1 — good
for gradually validating a risky change against real traffic.

This uses NGINX Ingress's built-in canary support: a second Ingress
resource, same host/path, marked `nginx.ingress.kubernetes.io/canary: "true"`
with a `canary-weight`. Start small and ramp up while watching metrics:

```bash
# 10% -> 25% -> 50% -> 100%, editing canary-weight each time:
kubectl annotate ingress service2-canary-ingress -n microapp \
  nginx.ingress.kubernetes.io/canary-weight="25" --overwrite
```

At 100%, promote: update the main `service2` Deployment's image to v2, then
delete the canary Deployment/Service/Ingress — v2 is now "stable."

**Note for interviews:** hand-rolled canary/blue-green like this is fine to
demonstrate the mechanics, but real production platforms typically use
**Argo Rollouts** or **Flagger** on top of this — they automate the
weight ramp-up, hook into Prometheus for automatic rollback on error-rate/
latency regressions, and remove the manual `kubectl patch` steps. Worth
naming as the "next step up" if asked how you'd harden this.

---

## Quick end-to-end verification checklist

```bash
kubectl get pods -n microapp                        # all Running, READY
kubectl get ingress -n microapp                      # ADDRESS populated
kubectl get certificate -n microapp                  # READY = True
curl -I https://ganga888.online/service1/            # 200, valid TLS
curl -I https://ganga888.online/service2/            # 200, valid TLS
kubectl get svc service1 -n microapp -o jsonpath='{.spec.selector}'  # confirm blue/green slot
```
