"""Controlled chroot comparison, in a disposable process and user namespace."""

import argparse
import ctypes
import json
import os
from pathlib import Path


def state():
    fields = dict(
        line.split(":", 1)
        for line in Path("/proc/self/status").read_text().splitlines()
        if ":" in line
    )
    return {
        "uid": os.getuid(),
        "user_namespace": os.readlink("/proc/self/ns/user"),
        **{
            key: fields[key].strip()
            for key in ("CapEff", "CapBnd", "NoNewPrivs", "Seccomp")
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-chroot", choices=["allowed", "denied"], required=True)
    args = parser.parse_args()
    before = state()
    assert before["uid"] != 0 and int(before["CapEff"], 16) == 0
    assert int(before["CapBnd"], 16) == 0
    assert before["NoNewPrivs"] == "1" and before["Seccomp"] == "2"
    libc = ctypes.CDLL(None, use_errno=True)
    libc.chroot.argtypes = [ctypes.c_char_p]
    libc.unshare.argtypes = [ctypes.c_int]
    # Parent must still be denied by the kernel even with the adapted seccomp.
    code = libc.chroot(b"/proc/self/fdinfo/")
    parent_errno = ctypes.get_errno() if code == -1 else 0
    assert code == -1, "Parent unexpectedly has chroot privilege"
    assert parent_errno == 1, "Unexpected parent chroot error"
    uid, gid = os.getuid(), os.getgid()
    code = libc.unshare(0x10000000)  # CLONE_NEWUSER, no host settings changed.
    if code == -1:
        print(
            json.dumps(
                {
                    "parent": before,
                    "parent_chroot_errno": parent_errno,
                    "namespace_errno": ctypes.get_errno(),
                }
            )
        )
        return 2
    Path("/proc/self/setgroups").write_text("deny")
    Path("/proc/self/uid_map").write_text(f"0 {uid} 1")
    Path("/proc/self/gid_map").write_text(f"0 {gid} 1")
    child = state()
    assert child["user_namespace"] != before["user_namespace"]
    assert child["uid"] == 0 and int(child["CapEff"], 16) & (1 << 18)
    assert child["NoNewPrivs"] == "1" and child["Seccomp"] == "2"
    # Creation grants capabilities only inside the new user namespace, including
    # a namespaced bounding set. This does not add Docker/container capabilities.
    code = libc.chroot(b"/proc/self/fdinfo/")
    child_errno = ctypes.get_errno() if code == -1 else 0
    if code == 0:
        os.chdir("/")
    print(
        json.dumps(
            {
                "parent": before,
                "parent_chroot_errno": parent_errno,
                "child": child,
                "namespace_chroot_errno": child_errno,
                "namespace_chroot_succeeded": code == 0,
            }
        )
    )
    if args.expect_chroot == "allowed":
        assert code == 0, "Adapted profile did not permit namespaced chroot"
    else:
        assert code == -1 and child_errno == 1, (
            "Official profile no longer denies chroot"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
