"""Fail closed before any lab navigation; never disable the Chromium sandbox."""

import argparse
import json
import os
from pathlib import Path

from network_policy import install_policy
from playwright.sync_api import Error, sync_playwright
from sandbox_result import classify_launch_error
from witnesses import verify_restrictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    status = Path("/proc/self/status").read_text()
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    assert os.getuid() != 0, "Browser must be non-root"
    assert int(fields["CapEff"].strip(), 16) == 0, "Unexpected capability"
    assert fields["NoNewPrivs"].strip() == "1", "NoNewPrivs must be enabled"
    assert fields["Seccomp"].strip() == "2", "Seccomp filter required"
    Path(os.environ["HOME"]).mkdir(mode=0o700, exist_ok=True)
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(chromium_sandbox=True)
        except Error as error:
            # This virgin browser contains no account, cookie, token or lab content.
            reason = classify_launch_error(str(error))
            print(
                json.dumps(
                    {
                        "stage": "sandbox-launch",
                        "sandbox_verified": False,
                        "reason": reason,
                        "network_restrictions_verified": False,
                        "lab_tls_verified": False,
                        "xss_allowed": False,
                    }
                )
            )
            # Diagnostic compatibility classification is not prerequisite validation.
            # Mandatory gate mode remains nonzero. Unknown failures always raise.
            return 0 if args.diagnostic else 2
        try:
            page = browser.new_page()
            page.goto("chrome://sandbox")
            evidence = page.locator("body").inner_text()
            print(json.dumps({"sandbox_status": evidence, "browser": browser.version}))
            # Launch success alone is insufficient: both namespace and seccomp layers.
            assert "Namespace Sandbox" in evidence and "Seccomp-BPF sandbox" in evidence
            rows = page.locator("tr").all_text_contents()
            assert any("Namespace Sandbox" in row and "Yes" in row for row in rows)
            assert any("Seccomp-BPF sandbox" in row and "Yes" in row for row in rows)
            page.close()
            verify_restrictions(browser, install_policy)
            print(
                json.dumps(
                    {
                        "sandbox_verified": True,
                        "network_restrictions_verified": True,
                        "lab_tls_verified": False,
                        "xss_allowed": False,
                    }
                )
            )
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
