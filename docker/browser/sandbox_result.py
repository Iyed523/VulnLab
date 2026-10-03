"""Classify only explicit Chromium sandbox failures; never hide tool errors."""


def classify_launch_error(message):
    if "No usable sandbox!" in message:
        return "no-usable-sandbox"
    if 'Check failed: sys_chroot("/proc/self/fdinfo/") == 0' in message:
        return "zygote-chroot-denied"
    raise RuntimeError("Unexpected browser execution error")
