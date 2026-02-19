# SentinelScope

This project uses **Google’s Online Boutique** microservices demo as the test system for our AI Agent Observability project.

We included **fixed Kubernetes manifests** so the system runs locally without debugging.

---

## Requirements

- Docker Desktop installed
- Kubernetes enabled in Docker Desktop
- kubectl installed

Check Kubernetes is running:
```bash
kubectl cluster-info
```

---

## Cloning Repo
Clone repository using recursive to get the online boutique cloned
```bash
git clone --recursive https://github.com/VamsiP23/AgentScope.git
cd AgentScope
```

## Run the System (3 steps)

### 1. Deploy Online Boutique
```bash
kubectl apply -f saved_manifests/online-boutique.yaml
```

---

### 2. Wait for pods to start
```bash
kubectl get pods
```

Wait until most pods say:
```
Running
```

---

### 3️. Open the frontend
```bash
kubectl port-forward svc/frontend 8080:80
```

Then go to:
👉 http://localhost:8080

Keep this terminal open while using the site.

---

## 4. Restart if Add-to-Cart breaks

Sometimes Redis or Cart service starts slowly.

Run:
```bash
kubectl rollout restart deploy/redis-cart
kubectl rollout restart deploy/cartservice
```

Wait ~30 seconds and refresh the site.

---

## 5. Stop the system
```bash
kubectl delete -f saved_manifests/online-boutique.yaml
```

---

## 6. Notes

- If frontend doesn’t load → restart port-forward
- If add-to-cart fails → restart redis-cart + cartservice
- EXTERNAL-IP pending is normal on Docker Desktop

---

## Authors
Aarnav Sawant  
Sri Vamsi Putti
