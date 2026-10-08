# Docker → Kubernetes with Minikube: Hands-on Lab

A step-by-step lab for Windows, Docker Desktop (WSL 2), PowerShell, VS Code, and Minikube.

## Learning objectives

- Build a Flask API and package it as a Docker image.
- Run and test the image locally.
- Create a local Kubernetes cluster with Minikube.
- Deploy the image using Kubernetes manifests.
- Expose the app, scale replicas, inspect logs, test self-healing, and roll out updates.

> **Architecture:** Flask source → Docker image → Minikube image store → Kubernetes Deployment (Pods) → Kubernetes Service → local browser.
>
> Kubernetes is the orchestrator; Minikube provides the local cluster.

## Phase 1 — Check prerequisites

- [ ] Install and start Docker Desktop with Linux containers and WSL 2 integration.
- [ ] Install Minikube and kubectl (if missing).
- [ ] Open **PowerShell** in VS Code (`Terminal → New Terminal`).

```powershell
wsl --status
docker --version
docker info --format '{{.OSType}}'
minikube version
kubectl version --client
```

**Expected:** Docker reports `linux`; Minikube and kubectl show installed versions. If a command is not recognized, install that tool before proceeding. Docker Desktop should be running.

- [ ] Start Minikube:

```powershell
minikube start --driver=docker --cpus=2 --memory=4096
minikube status
kubectl get nodes
kubectl get pods -A
```

**Expected:** The Minikube node becomes `Ready`. If startup fails, verify virtualization/WSL 2 and Docker Desktop, then retry.

## Phase 2 — Create the Flask application

- [ ] Create and open the project:

```powershell
mkdir docker-k8s-lab
cd docker-k8s-lab
code .
mkdir k8s
```

> If you downloaded this README, place it inside the `docker-k8s-lab` folder. If the folder already exists, open it instead of creating it again.

- [ ] Create `app.py`:

```python
import os
import socket
from flask import Flask, jsonify

app = Flask(__name__)

@app.get("/")
def home():
    return jsonify(
        message="Hello from Docker and Kubernetes!",
        version=os.getenv("APP_VERSION", "v1"),
        pod=socket.gethostname(),
    )

@app.get("/health")
def health():
    return jsonify(status="healthy"), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

- [ ] Create `requirements.txt`:

```text
flask==3.1.1
```

**Checkpoint:** You have `app.py` and `requirements.txt` in the project root.

## Phase 3 — Build and test with Docker

- [ ] Create `Dockerfile` (no extension):

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN useradd --create-home appuser
USER appuser
EXPOSE 5000
CMD ["python", "app.py"]
```

- [ ] Create `.dockerignore`:

```text
.git
.venv
__pycache__
*.pyc
.env
```

- [ ] Build and inspect the image:

```powershell
docker build -t flask-k8s-demo:v1 .
docker images
```

- [ ] Run and test the container:

```powershell
docker run -d --name flask-demo -p 5000:5000 flask-k8s-demo:v1
docker ps
curl.exe http://localhost:5000
curl.exe http://localhost:5000/health
```

**Expected:** The root endpoint returns JSON with a message, `version: v1`, and the container hostname; `/health` returns `healthy`.

- [ ] Stop and remove the standalone container:

```powershell
docker logs flask-demo
docker stop flask-demo
docker rm flask-demo
```

**Concept check:** The Dockerfile defines how to build the image; `docker run` creates a container from it. The `-p 5000:5000` flag publishes the container port to the Windows host.

## Phase 4 — Deploy the image to Kubernetes

- [ ] Load the locally built image into Minikube:

```powershell
minikube image load flask-k8s-demo:v1
```

> With Minikube's Docker driver, don't assume a host-built image is automatically available inside the Kubernetes node. `minikube image load` makes it available. `imagePullPolicy: Never` ensures Kubernetes uses the local image rather than trying a remote registry.

- [ ] Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flask-demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: flask-demo
  template:
    metadata:
      labels:
        app: flask-demo
    spec:
      containers:
        - name: flask-demo
          image: flask-k8s-demo:v1
          imagePullPolicy: Never
          ports:
            - containerPort: 5000
          env:
            - name: APP_VERSION
              value: "v1"
          readinessProbe:
            httpGet:
              path: /health
              port: 5000
            initialDelaySeconds: 3
            periodSeconds: 5
          resources:
            requests:
              cpu: "100m"
              memory: "64Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
```

- [ ] Create `k8s/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: flask-demo-service
spec:
  type: NodePort
  selector:
    app: flask-demo
  ports:
    - port: 80
      targetPort: 5000
      protocol: TCP
```

- [ ] Apply and verify:

```powershell
kubectl apply -f k8s/
kubectl rollout status deployment/flask-demo
kubectl get deployments
kubectl get pods -o wide
kubectl get services
```

**Expected:** Two Pods reach `Running` and `Ready`; one Service named `flask-demo-service` exists.

**Concept check:** A Deployment maintains the desired number of Pods. A Service provides stable networking to the Pods matching its selector.

## Phase 5 — Access, scale, and troubleshoot

- [ ] Expose the Service (keep this terminal open):

```powershell
minikube service flask-demo-service --url
```

Open the printed URL in a browser. On Windows with the Docker driver, the terminal may need to remain open to keep the tunnel available.

**Alternative** (use a separate terminal; keep it open):

```powershell
kubectl port-forward service/flask-demo-service 8080:80
```

Then visit `http://localhost:8080`.

- [ ] Scale from 2 to 4 replicas:

```powershell
kubectl scale deployment flask-demo --replicas=4
kubectl rollout status deployment/flask-demo
kubectl get pods -o wide
```

**Expected:** Four healthy Pods.

- [ ] Inspect logs and Pod details:

```powershell
kubectl logs deployment/flask-demo --all-pods=true --prefix=true
kubectl describe deployment flask-demo
kubectl get events --sort-by=.metadata.creationTimestamp
```

- [ ] Test self-healing: find a Pod name using `kubectl get pods`, then replace `YOUR_POD_NAME` below:

```powershell
kubectl delete pod YOUR_POD_NAME
kubectl get pods -w
```

**Expected:** Kubernetes creates a replacement Pod to restore the desired replica count. Press `Ctrl+C` to stop watching.

## Phase 6 — Roll out version 2 and roll back

- [ ] Change the message in `app.py` to `Hello from version 2!` and save.
- [ ] Build and load the new image:

```powershell
docker build -t flask-k8s-demo:v2 .
minikube image load flask-k8s-demo:v2
```

- [ ] Roll out version 2:

```powershell
kubectl set image deployment/flask-demo flask-demo=flask-k8s-demo:v2
kubectl set env deployment/flask-demo APP_VERSION=v2
kubectl rollout status deployment/flask-demo
kubectl rollout history deployment/flask-demo
```

**Expected:** The app reports the version 2 message and environment version `v2`. Because the image and environment were updated in separate commands, the rollout history may include two revisions.

- [ ] Roll back to the earlier image (explicitly, so the image and version variable stay aligned):

```powershell
kubectl set image deployment/flask-demo flask-demo=flask-k8s-demo:v1
kubectl set env deployment/flask-demo APP_VERSION=v1
kubectl rollout status deployment/flask-demo
```

**Expected:** The original app message and `v1` return. To practice native revision rollback separately, try `kubectl rollout undo deployment/flask-demo` and inspect the resulting Deployment; remember that each `set` command can create its own revision.

> **Important:** Imperative changes such as `kubectl scale`, `kubectl set image`, and `kubectl set env` modify the live Deployment, not your YAML files. Before treating manifests as your source of truth, update `k8s/deployment.yaml` to the final desired replica count, image tag, and environment values. Otherwise, a later `kubectl apply` may revert live settings.

## Troubleshooting quick reference

| Symptom | What to check |
|---|---|
| `docker` command fails | Docker Desktop running? WSL 2 / Linux containers enabled? |
| Minikube start fails | `docker info`, virtualization/WSL settings, available RAM |
| Pod says `ErrImageNeverPull` | Was the correct tag loaded with `minikube image load`? |
| Pod says `CrashLoopBackOff` | `kubectl logs POD_NAME` and `kubectl describe pod POD_NAME` |
| Service doesn't respond | `kubectl get pods`, `kubectl get endpointslices`, and port-forward output |
| App still shows v1 | Verify Deployment image tag, `APP_VERSION`, and image build contents |

## Cleanup

When finished, remove the Kubernetes resources:

```powershell
kubectl delete -f k8s/
minikube stop
```

To delete the entire local cluster and its state instead:

```powershell
minikube delete
```

> `minikube delete` is destructive for the local lab cluster. Your project source files remain in your VS Code folder.

## Final checklist

- [ ] Docker and Minikube installed and working
- [ ] Flask API created
- [ ] Docker image built and tested
- [ ] Image loaded into Minikube
- [ ] Deployment and Service applied
- [ ] Application reachable in browser
- [ ] Replicas scaled successfully
- [ ] Pod self-healing observed
- [ ] Version 2 deployed and version 1 restored
- [ ] Lab cleaned up (optional)

## Further practice

1. Add a liveness probe and compare it with readiness probes.
2. Move `APP_VERSION` into a ConfigMap.
3. Add a Secret for a non-sensitive practice value (do not commit real credentials).
4. Try `kubectl top pods` after enabling metrics-server: `minikube addons enable metrics-server`.
5. Push a versioned image to a registry and change `imagePullPolicy` to a suitable remote-pull policy.
6. Explore Ingress and rolling-update settings.

## References

- Docker getting started: https://docs.docker.com/get-started/
- Minikube start: https://minikube.sigs.k8s.io/docs/start/
- Kubernetes Deployments: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- Kubernetes Services: https://kubernetes.io/docs/concepts/services-networking/service/
