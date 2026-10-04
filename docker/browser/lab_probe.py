"""Mandatory M12.2 gate, fresh browser and local-only endpoints, no XSS."""

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

from network_policy import install_policy, navigate, origin
from network_result import connection_refusal, download_refusal
from playwright.async_api import Error, async_playwright
from sandbox_result import verify_sandbox_rows
from tls_result import tls_failure
from witnesses import verify_restrictions

LAB = "https://vulnerable.vulnlab.test:8443"
GOOD = "https://good.vulnlab.test:8443"
FORBIDDEN = "https://forbidden.vulnlab.test:8443"
UNKNOWN = "https://untrusted.vulnlab.test:8444"
WRONG = "https://wrong.vulnlab.test:8445"
CORRECT = "https://correct.vulnlab.test:8445"
STAGE = "trust"


def trust(both=False):
    home = Path(os.environ["HOME"])
    database = home / ".local/share/pki/nssdb"
    database.mkdir(parents=True, mode=0o700, exist_ok=False)
    subprocess.run(
        ["certutil", "-N", "--empty-password", "-d", f"sql:{database}"],
        capture_output=True,
        check=True,
        timeout=10,
    )
    for name in ("trusted", "untrusted") if both else ("trusted",):
        subprocess.run(
            [
                "certutil",
                "-A",
                "-d",
                f"sql:{database}",
                "-t",
                "C,,",
                "-n",
                f"M12.2-{name}",
                "-i",
                f"/run/trust/{name}.crt",
            ],
            capture_output=True,
            check=True,
            timeout=10,
        )
    assert all(path.suffix == ".crt" for path in Path("/run/trust").iterdir())
    os.environ["NODE_EXTRA_CA_CERTS"] = (
        "/run/trust/both.crt" if both else "/run/trust/trusted.crt"
    )


async def sandbox(browser):
    page = await browser.new_page()
    await page.goto("chrome://sandbox")
    rows = await page.locator("tr").evaluate_all(
        "rows => rows.map(r => Array.from(r.cells, c => c.innerText.trim()))"
    )
    layers = verify_sandbox_rows(rows)
    cdp = await browser.new_browser_cdp_session()
    processes = (await cdp.send("SystemInfo.getProcessInfo"))["processInfo"]
    controls = []
    for process in processes:
        if process["type"] not in {"browser", "renderer"}:
            continue
        fields = dict(
            line.split(":", 1)
            for line in Path(f"/proc/{process['id']}/status").read_text().splitlines()
            if ":" in line
        )
        uid = int(fields["Uid"].split()[0])
        assert uid != 0 and int(fields["CapEff"], 16) == int(fields["CapPrm"], 16) == 0
        assert fields["NoNewPrivs"].strip() == "1" and fields["Seccomp"].strip() == "2"
        controls.append(
            {
                "type": process["type"],
                "uid": uid,
                "CapEff": "0",
                "CapPrm": "0",
                "NoNewPrivs": 1,
                "Seccomp": 2,
                "Seccomp_filters": int(fields["Seccomp_filters"]),
            }
        )
    filters = next(p["Seccomp_filters"] for p in controls if p["type"] == "browser")
    renderers = [p for p in controls if p["type"] == "renderer"]
    assert renderers and all(
        p["Seccomp_filters"] >= 2 and p["Seccomp_filters"] > filters for p in renderers
    )
    await page.close()
    await cdp.detach()
    return {"layers": layers, "processes": controls}


async def context(browser):
    return await browser.new_context(
        ignore_https_errors=False, service_workers="block", accept_downloads=False
    )


async def connection(browser, url, engine, expected=None):
    global STAGE
    STAGE = "tls-" + engine + "-" + (expected or "positive")
    async with await context(browser) as ctx:
        errors = []
        if engine == "mediator":
            await install_policy(ctx, {origin(url)}, errors)
        page = await ctx.new_page()
        try:
            response = await page.goto(url + "/positive", timeout=12000)
        except Error as caught:
            message = str(caught)
            if expected is None:
                raise RuntimeError(
                    "Required local HTTPS positive control failed"
                ) from None
            if engine == "mediator":
                assert len(errors) == 1, "Mediator did not propagate the TLS failure"
                message = str(errors[0])
            assert tls_failure(message, engine) == expected
            assert (
                "Local M12.2 witness" not in await page.locator("body").inner_text()
            ), "Unverified TLS response was rendered"
            return {"refused": expected, "response_fulfilled": False}
        assert expected is None, "Invalid TLS identity unexpectedly accepted"
        assert not errors and response.status == 200
        assert await page.locator("h1").inner_text() == "Local M12.2 witness"
        return {"status": 200, "verified": True}


def direct_network():
    result = {}
    for name, port in (("APP", 8000), ("DB", 5432), ("REDIS", 6379)):
        ip = os.environ[name + "_PROBE_IP"]
        socket.inet_aton(ip)  # Numeric IP only: DNS refusal cannot pass.
        try:
            with socket.create_connection((ip, port), timeout=3):
                raise AssertionError("Direct internal service unexpectedly reachable")
        except OSError as error:
            result[name.lower()] = connection_refusal(error)
    return result


def stats():
    with urlopen("http://tls-witness:8446/stats", timeout=3) as response:
        return json.load(response)


async def connected_witnesses(browser):
    global STAGE
    # Native positive reachability; fresh context and valid trusted certificate.
    await connection(browser, FORBIDDEN, "chromium")
    async with await context(browser) as ctx:
        page = await ctx.new_page()
        await page.goto(GOOD + "/positive")
        opened = await page.evaluate(
            """url => new Promise(resolve => {
            const ws = new WebSocket(url); const timer = setTimeout(() => resolve(false), 5000);
            ws.onopen = () => { clearTimeout(timer); ws.close(); resolve(true); };
            ws.onerror = () => { clearTimeout(timer); resolve(false); };
        })""",
            FORBIDDEN.replace("https:", "wss:") + "/socket",
        )
        assert opened
    before = stats()
    async with await context(browser) as ctx:
        errors = []
        decisions = []
        await install_policy(ctx, {origin(GOOD)}, errors, decisions)
        page = await ctx.new_page()
        assert (await page.goto(GOOD + "/relative")).status == 200
        for url in (
            FORBIDDEN + "/denied",
            GOOD + "/redirect",
            GOOD + "/chain",
            GOOD.replace("https:", "http:") + "/cleartext",
        ):
            STAGE = "policy-direct-redirect-cleartext"
            negative = await ctx.new_page()
            try:
                await negative.goto(url, timeout=12000)
            except Error as error:
                assert "net::ERR_BLOCKED_BY_CLIENT" in str(error)
            else:
                raise AssertionError("Forbidden destination or redirect accepted")
            finally:
                await negative.close()
        STAGE = "policy-userinfo"
        try:
            await navigate(
                page,
                GOOD.replace("https://", "https://user@") + "/userinfo",
                {origin(GOOD)},
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Raw userinfo navigation accepted")
        STAGE = "policy-websocket"
        closed = await page.evaluate(
            """url => new Promise(resolve => {
            const ws = new WebSocket(url); const timer = setTimeout(() => resolve(false), 5000);
            ws.onopen = () => { clearTimeout(timer); ws.close(); resolve(false); };
            ws.onclose = ws.onerror = () => { clearTimeout(timer); resolve(true); };
        })""",
            FORBIDDEN.replace("https:", "wss:") + "/socket",
        )
        assert closed and not errors
        STAGE = "policy-download"
        downloads = []
        download_page = await ctx.new_page()
        download_page.on("download", lambda download: downloads.append(download))
        try:
            STAGE = "policy-download-navigation"
            await download_page.goto(GOOD + "/download-mediated")
        except Error as error:
            assert "net::ERR_BLOCKED_BY_CLIENT" in str(
                error
            ) or "net::ERR_FAILED" in str(error)
        else:
            raise AssertionError("Attachment was fulfilled instead of blocked")
        await download_page.close()
        STAGE = "policy-download-decision"
        print(
            json.dumps(
                {
                    "attachment_decisions": decisions,
                    "download_events": len(downloads),
                    "fetch_error_types": [type(error).__name__ for error in errors],
                }
            ),
            flush=True,
        )
        assert decisions == ["attachment-refused-before-fulfill"]
        STAGE = "policy-download-events"
        assert not downloads and not errors
        STAGE = "policy-service-worker-restore"
        await navigate(page, GOOD + "/positive", {origin(GOOD)})
        STAGE = "policy-service-worker"
        async with page.expect_console_message(
            predicate=lambda message: (
                "Service Worker registration blocked by Playwright" in message.text
            ),
            timeout=5000,
        ):
            await page.evaluate(
                "() => { navigator.serviceWorker.register('/worker.js').catch(() => {}); }"
            )
        assert not ctx.service_workers
    after = stats()
    assert before.get("forbidden.vulnlab.test", 0) == after.get(
        "forbidden.vulnlab.test", 0
    )
    assert before.get("forbidden.vulnlab.test:ws", 0) == after.get(
        "forbidden.vulnlab.test:ws", 0
    )
    return {
        "positive_https": True,
        "positive_websocket": True,
        "relative_redirect": True,
        "direct_redirect_chain_cleartext_userinfo_refused": True,
        "websocket_refused": True,
        "download_not_persisted": True,
        "mediator_attachment_refused": True,
        "service_workers_registration_blocked": True,
        "forbidden_additional_requests": 0,
    }


async def native_download(browser):
    global STAGE
    STAGE = "native-download"
    async with await context(browser) as ctx:
        page = await ctx.new_page()
        message = ""
        async with page.expect_download(timeout=10000) as info:
            try:
                await page.goto(GOOD + "/download")
            except Error as error:
                message = str(error)
        download = await info.value
        return download_refusal(message, await download.failure())


async def lab_flow(browser):
    global STAGE
    STAGE = "lab-native-health-forms-resources"
    native = {}
    async with await context(browser) as ctx:
        page = await ctx.new_page()
        response = await navigate(page, LAB + "/healthz", {origin(LAB)})
        assert response.status == 200 and await response.json() == {"status": "ok"}
        for path in ("/login", "/register"):
            assert (await navigate(page, LAB + path, {origin(LAB)})).status == 200
            assert await page.locator("form").count() == 1
        assert (
            await navigate(page, LAB + "/static/css/lab.css", {origin(LAB)})
        ).status == 200
        native = {"healthz": True, "forms": True, "stylesheet": True}
    async with await context(browser) as ctx:
        errors = []
        STAGE = "lab-mediated-health-login"
        await install_policy(ctx, {origin(LAB)}, errors)
        page = await ctx.new_page()
        assert (await navigate(page, LAB + "/healthz", {origin(LAB)})).status == 200
        resources = []
        page.on(
            "response",
            lambda response: resources.append((response.url, response.status)),
        )
        await navigate(page, LAB + "/login", {origin(LAB)})
        await page.locator('[name="username"]').fill("alice")
        await page.locator('[name="password"]').fill("demo-Alice-only!")
        STAGE = "lab-login-submit"
        await page.get_by_role("button", name="Log in", exact=True).click()
        STAGE = "lab-login-account-heading"
        await page.get_by_role("heading", name="Your account").wait_for()
        # Manual redirect mediation returns the final document at the original
        # navigation URL. Canonical navigation is explicit, never assumed.
        STAGE = "lab-own-account"
        await navigate(page, LAB + "/account", {origin(LAB)})
        assert await page.get_by_role("heading", name="Your account").count() == 1
        assert await page.locator("dd").first.inner_text() == "alice"
        await page.get_by_role("button", name="Log out", exact=True).click()
        STAGE = "lab-logout"
        await page.get_by_role("heading", name="Log in", exact=True).wait_for()
        await navigate(page, LAB + "/account", {origin(LAB)})
        assert await page.get_by_role("heading", name="Log in", exact=True).count() == 1
        await navigate(page, LAB + "/login", {origin(LAB)})
        assert await page.locator('[name="username"]').count() == 1
        assert any(
            url == LAB + "/static/css/lab.css" and status == 200
            for url, status in resources
        )
        assert not errors
    return {
        "chromium_direct": native,
        "mediated_healthz_resources_login_own_account_logout": True,
        "cookies_tokens_memory_only": True,
        "idor_used": False,
    }


async def run(both):
    global STAGE
    trust(both)
    STAGE = "sandbox-launch"
    fields = dict(
        line.split(":", 1)
        for line in Path("/proc/self/status").read_text().splitlines()
        if ":" in line
    )
    assert (
        os.getuid() != 0 and int(fields["CapEff"], 16) == int(fields["CapBnd"], 16) == 0
    )
    assert fields["NoNewPrivs"].strip() == "1" and fields["Seccomp"].strip() == "2"
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            chromium_sandbox=True, channel="chromium"
        )
        try:
            if both:
                for engine in ("chromium", "mediator"):
                    await connection(browser, UNKNOWN, engine)
                return {
                    "untrusted_witness_positive_with_own_authority": True,
                    "both_engines": True,
                }
            STAGE = "sandbox-before"
            initial = await sandbox(browser)
            tls = {}
            for engine in ("chromium", "mediator"):
                STAGE = "tls-" + engine
                tls[engine] = {
                    "trusted_correct": await connection(browser, GOOD, engine),
                    "unknown_authority": await connection(
                        browser, UNKNOWN, engine, "authority"
                    ),
                    "wrong_name": await connection(browser, WRONG, engine, "name"),
                    "same_certificate_correct_name": await connection(
                        browser, CORRECT, engine
                    ),
                }
            print(
                "Both TLS paths: positive, authority refusal, hostname refusal verified",
                flush=True,
            )
            STAGE = "direct-internal-network"
            network = direct_network()
            STAGE = "connected-witnesses"
            download = await native_download(browser)
            witnesses = await connected_witnesses(browser)
            STAGE = "loopback-witnesses"
            loopback = await verify_restrictions(browser, install_policy)
            STAGE = "lab-flow"
            journey = await lab_flow(browser)
            STAGE = "sandbox-after"
            final = await sandbox(browser)
            return {
                "sandbox_verified": True,
                "sandbox_before": initial,
                "sandbox_after": final,
                "tls": tls,
                "direct_internal_network": network,
                "connected_witnesses": witnesses,
                "native_download_refusal": download,
                "m121_loopback_witnesses": loopback,
                "lab_flow": journey,
                "lab_tls_verified": True,
                "xss_allowed": False,
                "browser": browser.version,
            }
        finally:
            await browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trust-both", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args.trust_both))
        if not args.trust_both:
            environment = dict(os.environ, HOME="/tmp/browser-positive-home")
            child = subprocess.run(
                [sys.executable, __file__, "--trust-both"],
                env=environment,
                capture_output=True,
                text=True,
                timeout=45,
                check=True,
            )
            result["unknown_authority_positive_control"] = json.loads(child.stdout)
        print(json.dumps(result))
    except Exception as error:
        trace = error.__traceback__
        site = "unknown"
        while trace is not None:
            if Path(trace.tb_frame.f_code.co_filename).name in {
                "lab_probe.py",
                "network_policy.py",
            }:
                site = f"{trace.tb_frame.f_code.co_name}:{trace.tb_lineno}"
            trace = trace.tb_next
        # Never print exception/traceback: a Playwright auth call log may contain
        # the fictitious password, cookie or CSRF token. The gate still fails.
        print(
            json.dumps(
                {
                    "stage": STAGE,
                    "exception_type": type(error).__name__,
                    "failure_site": site,
                    "verified": False,
                    "xss_allowed": False,
                }
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
