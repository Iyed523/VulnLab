"""Fail closed before any lab navigation; never disable the Chromium sandbox."""

import asyncio
import json
import os
from pathlib import Path

from network_policy import install_policy
from playwright.async_api import Error, async_playwright
from sandbox_result import classify_launch_error, verify_sandbox_rows
from witnesses import verify_restrictions


async def main():
    status = Path("/proc/self/status").read_text()
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    assert os.getuid() != 0, "Browser must be non-root"
    assert int(fields["CapEff"].strip(), 16) == 0, "Unexpected capability"
    assert int(fields["CapBnd"].strip(), 16) == 0, "Unexpected capability bounding set"
    assert fields["NoNewPrivs"].strip() == "1", "NoNewPrivs must be enabled"
    assert fields["Seccomp"].strip() == "2", "Seccomp filter required"
    Path(os.environ["HOME"]).mkdir(mode=0o700, exist_ok=True)
    async with async_playwright() as playwright:
        try:
            # Full Chromium supports chrome://sandbox; headless-shell does not.
            browser = await playwright.chromium.launch(
                chromium_sandbox=True, channel="chromium"
            )
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
            # A recognized diagnostic is still a failed mandatory prerequisite.
            return 2
        try:
            page = await browser.new_page()
            await page.goto("chrome://sandbox")
            evidence = await page.locator("body").inner_text()
            print(json.dumps({"sandbox_status": evidence, "browser": browser.version}))
            # Launch success alone is insufficient: both namespace and seccomp layers.
            rows = await page.locator("tr").evaluate_all(
                "rows => rows.map(row => Array.from(row.cells, c => c.innerText.trim()))"
            )
            sandbox = verify_sandbox_rows(rows)
            cdp = await browser.new_browser_cdp_session()
            processes = await cdp.send("SystemInfo.getProcessInfo")
            process_controls = []
            for process in processes["processInfo"]:
                if process["type"] not in {"browser", "renderer"}:
                    continue
                proc = Path(f"/proc/{process['id']}/status")
                proc_fields = dict(
                    line.split(":", 1)
                    for line in proc.read_text().splitlines()
                    if ":" in line
                )
                assert int(proc_fields["CapEff"].strip(), 16) == 0
                assert int(proc_fields["CapPrm"].strip(), 16) == 0
                uid = int(proc_fields["Uid"].split()[0])
                assert uid != 0
                assert proc_fields["NoNewPrivs"].strip() == "1"
                assert proc_fields["Seccomp"].strip() == "2"
                if process["type"] == "renderer":
                    assert int(proc_fields["Seccomp_filters"].strip()) >= 2
                process_controls.append(
                    {
                        "type": process["type"],
                        "uid": uid,
                        "CapEff": "0",
                        "CapPrm": "0",
                        "NoNewPrivs": 1,
                        "Seccomp": 2,
                        "Seccomp_filters": int(proc_fields["Seccomp_filters"].strip()),
                    }
                )
            assert any(process["type"] == "renderer" for process in process_controls)
            browser_filters = next(
                process["Seccomp_filters"]
                for process in process_controls
                if process["type"] == "browser"
            )
            assert all(
                process["Seccomp_filters"] > browser_filters
                for process in process_controls
                if process["type"] == "renderer"
            ), "Renderer must have an additional seccomp filter"
            await page.close()
            network = await verify_restrictions(browser, install_policy)
            print(
                json.dumps(
                    {
                        "sandbox_verified": True,
                        "sandbox_layers": sandbox,
                        "process_controls": process_controls,
                        "network_restrictions_verified": True,
                        "local_witnesses": network,
                        "lab_tls_verified": False,
                        "xss_allowed": False,
                    }
                )
            )
        finally:
            await browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
