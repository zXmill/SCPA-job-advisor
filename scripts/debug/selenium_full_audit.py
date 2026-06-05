"""Selenium/Chrome browser audit for SCPA.

This script intentionally avoids seeded credentials unless they are supplied by
the caller. It audits public and unauthenticated protected-route behavior,
captures screenshots, console logs, and Chrome performance network failures,
then writes a compact report under reports/debug/browser.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "frontend" / "src" / "app"
DEFAULT_OUTPUT = ROOT / "reports" / "debug" / "browser"

ERROR_TEXT = re.compile(
    r"\b(error|exception|failed|unauthorized|forbidden|not found|hydration|"
    r"application error|runtime error)\b",
    re.IGNORECASE,
)


@dataclass
class PageAudit:
    route: str
    url: str
    title: str = ""
    status: str = "unknown"
    load_ms: float = 0.0
    screenshot: str = ""
    body_text_length: int = 0
    visible_error_text: list[str] = field(default_factory=list)
    console_error_count: int = 0
    console_warning_count: int = 0
    network_failure_count: int = 0
    button_count: int = 0
    form_count: int = 0
    input_count: int = 0
    link_count: int = 0
    blank_page: bool = False
    hydration_error: bool = False
    notes: list[str] = field(default_factory=list)


def safe_name(route: str) -> str:
    name = route.strip("/") or "home"
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", name)[:120]


def route_from_page(page_file: Path) -> str:
    rel = page_file.parent.relative_to(APP_DIR)
    if str(rel) == ".":
        return "/"
    parts = []
    for part in rel.parts:
        if part.startswith("(") and part.endswith(")"):
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def discover_routes(job_id: str | None) -> list[str]:
    routes = {
        "/",
        "/auth",
        "/dashboard",
        "/profile",
        "/recommendations",
        "/analytics",
        "/apply",
        "/onboarding",
    }
    if APP_DIR.exists():
        for page in APP_DIR.rglob("page.tsx"):
            routes.add(route_from_page(page))

    resolved: set[str] = set()
    for route in routes:
        if "[" not in route:
            resolved.add(route)
            continue
        if route == "/jobs/[id]" and job_id:
            resolved.add(f"/jobs/{job_id}")
        elif route == "/jobs/[id]":
            resolved.add("/jobs/debug-missing-job")
        else:
            resolved.add(re.sub(r"\[[^\]]+\]", "debug", route))
    return sorted(resolved, key=lambda item: (item.count("/"), item))


def try_fetch_first_job_id(api_base: str) -> str | None:
    url = f"{api_base.rstrip('/')}/api/jobs?limit=1"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=5) as response:  # noqa: S310 - local/debug URL from CLI
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError):
        return None

    candidates: list[dict[str, Any]] = []
    if isinstance(payload, list):
        candidates = [item for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        for key in ("jobs", "items", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates = [item for item in value if isinstance(item, dict)]
                break

    for item in candidates:
        job_id = item.get("id") or item.get("job_id")
        if job_id:
            return str(job_id)
    return None


def clear_logs(driver: webdriver.Chrome) -> None:
    for log_type in ("browser", "performance"):
        try:
            driver.get_log(log_type)
        except WebDriverException:
            continue


def collect_logs(driver: webdriver.Chrome) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    browser_logs: list[dict[str, Any]] = []
    perf_logs: list[dict[str, Any]] = []
    try:
        browser_logs = driver.get_log("browser")
    except WebDriverException:
        pass
    try:
        perf_logs = driver.get_log("performance")
    except WebDriverException:
        pass
    return browser_logs, perf_logs


def parse_network_failures(route: str, perf_logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for entry in perf_logs:
        try:
            message = json.loads(entry.get("message", "{}")).get("message", {})
        except json.JSONDecodeError:
            continue
        method = message.get("method")
        params = message.get("params", {})
        if method == "Network.responseReceived":
            response = params.get("response", {})
            status = int(response.get("status") or 0)
            if status >= 400:
                failures.append(
                    {
                        "route": route,
                        "type": "response",
                        "status": status,
                        "url": response.get("url", ""),
                        "mimeType": response.get("mimeType", ""),
                    }
                )
        elif method == "Network.loadingFailed":
            failures.append(
                {
                    "route": route,
                    "type": "loadingFailed",
                    "errorText": params.get("errorText", ""),
                    "requestId": params.get("requestId", ""),
                }
            )
    return failures


def visible_error_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if line and ERROR_TEXT.search(line):
            lines.append(line[:300])
    return lines[:10]


def write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def audit_page(
    driver: webdriver.Chrome,
    base_url: str,
    output_dir: Path,
    route: str,
    settle_seconds: float,
) -> tuple[PageAudit, list[dict[str, Any]], list[dict[str, Any]]]:
    url = f"{base_url.rstrip('/')}{route}"
    page = PageAudit(route=route, url=url)
    clear_logs(driver)
    started = time.perf_counter()
    try:
        driver.get(url)
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") in {"interactive", "complete"}
        )
        time.sleep(settle_seconds)
        page.status = "loaded"
    except TimeoutException:
        page.status = "timeout"
        page.notes.append("document.readyState did not settle within timeout")
    except WebDriverException as exc:
        page.status = "webdriver_error"
        page.notes.append(str(exc)[:500])
    page.load_ms = round((time.perf_counter() - started) * 1000, 2)

    try:
        page.title = driver.title
        body = driver.find_element(By.TAG_NAME, "body")
        text = body.text or ""
        page.body_text_length = len(text.strip())
        page.visible_error_text = visible_error_lines(text)
        page.blank_page = page.body_text_length < 20
        page.button_count = len(driver.find_elements(By.TAG_NAME, "button"))
        page.form_count = len(driver.find_elements(By.TAG_NAME, "form"))
        page.input_count = len(driver.find_elements(By.TAG_NAME, "input"))
        page.link_count = len(driver.find_elements(By.TAG_NAME, "a"))
    except WebDriverException as exc:
        page.notes.append(f"dom inspection failed: {str(exc)[:300]}")

    screenshot_path = output_dir / "screenshots" / f"{safe_name(route)}.png"
    try:
        driver.save_screenshot(str(screenshot_path))
        page.screenshot = str(screenshot_path.relative_to(ROOT))
    except WebDriverException as exc:
        page.notes.append(f"screenshot failed: {str(exc)[:300]}")

    browser_logs, perf_logs = collect_logs(driver)
    console_errors = [log for log in browser_logs if log.get("level") == "SEVERE"]
    console_warnings = [log for log in browser_logs if log.get("level") == "WARNING"]
    page.console_error_count = len(console_errors)
    page.console_warning_count = len(console_warnings)
    page.hydration_error = any("hydration" in str(log.get("message", "")).lower() for log in browser_logs)

    network_failures = parse_network_failures(route, perf_logs)
    page.network_failure_count = len(network_failures)

    for log in browser_logs:
        log["route"] = route
    return page, browser_logs, network_failures


def build_driver(headless: bool, width: int, height: int, chrome_binary: str | None) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})
    if chrome_binary:
        options.binary_location = chrome_binary
    return webdriver.Chrome(options=options)


def perform_login(driver: WebDriver, base_url: str, email: str, password: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "attempted": True,
        "email": email,
        "success": False,
        "has_token": False,
        "current_url": "",
        "error": "",
    }
    try:
        driver.get(f"{base_url.rstrip('/')}/auth")
        WebDriverWait(driver, 20).until(lambda d: d.find_elements(By.CSS_SELECTOR, "input"))
        email_input = driver.find_element(By.CSS_SELECTOR, "input[type='email'], input[name='email']")
        password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password'], input[name='password']")
        email_input.clear()
        email_input.send_keys(email)
        password_input.clear()
        password_input.send_keys(password)
        submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit.click()
        WebDriverWait(driver, 20).until(
            lambda d: bool(
                d.execute_script("return localStorage.getItem('scpa_token') || localStorage.getItem('token')")
            )
            or "/dashboard" in d.current_url
            or "/onboarding" in d.current_url
        )
        result["current_url"] = driver.current_url
        result["has_token"] = bool(
            driver.execute_script("return localStorage.getItem('scpa_token') || localStorage.getItem('token')")
        )
        result["success"] = result["has_token"] or "/dashboard" in driver.current_url or "/onboarding" in driver.current_url
    except WebDriverException as exc:
        result["current_url"] = getattr(driver, "current_url", "")
        result["error"] = str(exc)[:500]
    return result


def markdown_report(
    pages: list[PageAudit],
    output_dir: Path,
    base_url: str,
    api_base: str,
    job_id: str | None,
    started_at: str,
    auth_result: dict[str, Any],
) -> str:
    failures = [page for page in pages if page.console_error_count or page.network_failure_count or page.blank_page]
    lines = [
        "# Selenium Browser Audit",
        "",
        f"- Started: {started_at}",
        f"- Frontend base URL: `{base_url}`",
        f"- API base URL: `{api_base}`",
        f"- Sample job id: `{job_id or 'not found'}`",
        f"- Auth attempted: `{auth_result.get('attempted', False)}`",
        f"- Auth success: `{auth_result.get('success', False)}`",
        f"- Routes audited: {len(pages)}",
        f"- Pages with console/network/blank-page findings: {len(failures)}",
        "",
        "## Route Results",
        "",
        "| Route | Status | Load ms | Console errors | Network failures | Blank | Screenshot |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for page in pages:
        screenshot = page.screenshot.replace("\\", "/") if page.screenshot else ""
        lines.append(
            f"| `{page.route}` | {page.status} | {page.load_ms} | "
            f"{page.console_error_count} | {page.network_failure_count} | "
            f"{'yes' if page.blank_page else 'no'} | `{screenshot}` |"
        )
    lines.extend(["", "## Findings", ""])
    if not failures:
        lines.append("- No console errors, network failures, or blank pages were detected.")
    else:
        for page in failures:
            detail = []
            if page.console_error_count:
                detail.append(f"{page.console_error_count} console errors")
            if page.network_failure_count:
                detail.append(f"{page.network_failure_count} network failures")
            if page.blank_page:
                detail.append("blank page")
            lines.append(f"- `{page.route}`: {', '.join(detail)}.")
            for text in page.visible_error_text[:3]:
                lines.append(f"  - Visible text: {text}")
    lines.extend(
        [
            "",
            "## Auth Note",
            "",
            "No credentials are used unless `--email` and `--password` are supplied. Passwords are never written to reports. Without credentials, protected routes are audited in no-token mode and should redirect or show controlled auth states.",
            "",
            "## Artifact Files",
            "",
            f"- Summary JSON: `{(output_dir / 'summary.json').relative_to(ROOT)}`",
            f"- Console logs: `{(output_dir / 'console.ndjson').relative_to(ROOT)}`",
            f"- Network failures: `{(output_dir / 'network_failures.ndjson').relative_to(ROOT)}`",
            f"- Screenshots: `{(output_dir / 'screenshots').relative_to(ROOT)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Selenium browser audit for SCPA.")
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--api-base", default="http://localhost:9000")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--settle-seconds", type=float, default=1.0)
    parser.add_argument("--chrome-binary", default=None)
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    output_dir = args.output.resolve()
    (output_dir / "screenshots").mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    job_id = try_fetch_first_job_id(args.api_base)
    routes = discover_routes(job_id)
    auth_result: dict[str, Any] = {"attempted": False, "success": False, "has_token": False}

    pages: list[PageAudit] = []
    all_console: list[dict[str, Any]] = []
    all_network_failures: list[dict[str, Any]] = []

    driver = build_driver(args.headless, args.width, args.height, args.chrome_binary)
    try:
        driver.set_page_load_timeout(30)
        driver.get(args.base_url)
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
        if args.email and args.password:
            auth_result = perform_login(driver, args.base_url, args.email, args.password)
            pages_note = "credentials supplied; authenticated route audit" if auth_result.get("success") else "credentials supplied; login failed"
        elif args.email or args.password:
            pages_note = "incomplete credentials supplied; audited in no-token mode"
        else:
            pages_note = "no credentials supplied; audited in no-token mode"

        for route in routes:
            page, console_logs, network_failures = audit_page(
                driver,
                args.base_url,
                output_dir,
                route,
                args.settle_seconds,
            )
            page.notes.append(pages_note)
            pages.append(page)
            all_console.extend(console_logs)
            all_network_failures.extend(network_failures)
    finally:
        driver.quit()

    summary = {
        "started_at": started_at,
        "base_url": args.base_url,
        "api_base": args.api_base,
        "auth": auth_result,
        "job_id": job_id,
        "routes": routes,
        "pages": [asdict(page) for page in pages],
        "totals": {
            "pages": len(pages),
            "console_errors": sum(page.console_error_count for page in pages),
            "console_warnings": sum(page.console_warning_count for page in pages),
            "network_failures": sum(page.network_failure_count for page in pages),
            "blank_pages": sum(1 for page in pages if page.blank_page),
            "hydration_errors": sum(1 for page in pages if page.hydration_error),
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_ndjson(output_dir / "console.ndjson", all_console)
    write_ndjson(output_dir / "network_failures.ndjson", all_network_failures)
    (output_dir / "browser_audit.md").write_text(
        markdown_report(pages, output_dir, args.base_url, args.api_base, job_id, started_at, auth_result),
        encoding="utf-8",
    )

    print(json.dumps(summary["totals"], indent=2))
    return 1 if summary["totals"]["console_errors"] or summary["totals"]["blank_pages"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
