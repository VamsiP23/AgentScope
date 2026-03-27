import subprocess



def run_kubectl(args: list[str], capture: bool = False) -> str:
    proc = subprocess.run(
        ["kubectl", *args],
        capture_output=capture,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or "kubectl failed"
        raise RuntimeError(err)
    return (proc.stdout or "").strip()


def kubectl_apply_manifest(yaml_text: str) -> str:
    proc = subprocess.run(
        ["kubectl", "apply", "-f", "-"],
        input=yaml_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or "kubectl apply failed"
        raise RuntimeError(err)
    return proc.stdout.strip()


def kubectl_delete_manifest(yaml_text: str) -> str:
    proc = subprocess.run(
        ["kubectl", "delete", "-f", "-", "--ignore-not-found"],
        input=yaml_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or "kubectl delete failed"
        raise RuntimeError(err)
    return proc.stdout.strip()



def check_kubectl_chaosemesh_fault_status(resource: str, namespace: str) -> bool:
    output = run_kubectl(
        ["get", resource, "-n", namespace, "-o", "name"],
        capture=True,
    )
    return bool(output.strip())
    
