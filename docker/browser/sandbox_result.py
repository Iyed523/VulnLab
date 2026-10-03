"""Classify only explicit Chromium sandbox failures; never hide tool errors."""


def classify_launch_error(message):
    if "No usable sandbox!" in message:
        return "no-usable-sandbox"
    if 'Check failed: sys_chroot("/proc/self/fdinfo/") == 0' in message:
        return "zygote-chroot-denied"
    raise RuntimeError("Unexpected browser execution error")


def verify_sandbox_rows(rows):
    """Exact Chromium 153 diagnostics, not a substring that could match 'No'."""
    values = dict(rows)
    required = {
        "Layer 1 Sandbox": "Namespace",
        "PID namespaces": "Yes",
        "Network namespaces": "Yes",
        "Seccomp-BPF sandbox": "Yes",
        "Seccomp-BPF sandbox supports TSYNC": "Yes",
    }
    for label, expected in required.items():
        if values.get(label) != expected:
            raise RuntimeError(f"Unverified Chromium sandbox prerequisite: {label}")
    return required
