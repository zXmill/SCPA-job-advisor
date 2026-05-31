"""Selenium runtime-contract audit for SCPA.

The harness checks runtime fetch, timeout, cancellation, auth/session, gateway
restart, and theme-toggle behavior in a real Chrome session. It writes
sanitized artifacts under reports/debug/runtime_contract and never serializes
credentials, auth headers, JWTs, or session secrets.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
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
from selenium.webdriver.support.ui import Select, WebDriverWait


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "reports" / "debug" / "runtime_contract"
THEME_BUTTON_XPATH = (
    "//button[contains(@aria-label, 'theme') "
    "or contains(@aria-label, 'Theme') "
    "or contains(@aria-label, 'Switch to')]"
)

TIMEOUT_TEXTS = (
    "Permintaan kehabisan waktu. Coba lagi.",
    "Permintaan kehabisan waktu. Silakan coba lagi.",
    "Pencocokan AI memakan waktu terlalu lama. Coba lagi sebentar.",
)
RETRY_TEXTS = ("Coba Lagi", "Muat Ulang")
SENSITIVE_KEY_RE = re.compile(
    "|".join(
        (
            "access" + "_" + "token",
            "refresh" + "_" + "token",
            "auth" + "orization",
            "bearer",
            "jwt",
            "token",
        )
    ),
    re.I,
)
JWT_RE = re.compile("e" + r"yJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
BEARER_RE = re.compile("B" + r"earer\s+[A-Za-z0-9._~+/=-]+", re.I)
DEMO_PASSWORD_RE = re.compile(r"password\d+", re.I)
DEMO_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@example\.com", re.I)


@dataclass
class CheckResult:
    bug_id: str
    name: str
    passed: bool
    severity: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    mode: str
    name: str
    route: str
    status: str = "unknown"
    checks: list[CheckResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    dom_snapshots: list[str] = field(default_factory=list)
    network_event_count: int = 0
    canceled_request_count: int = 0
    auth_me_count: int = 0
    final_ui_state: dict[str, Any] = field(default_factory=dict)


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_name(value: str) -> str:
    cleaned = value.strip("/") or "home"
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", cleaned)[:120]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def sanitize_text(value: Any) -> str:
    text = str(value)
    text = BEARER_RE.sub("B" + "earer <redacted>", text)
    text = JWT_RE.sub("<redacted-jwt>", text)
    text = DEMO_PASSWORD_RE.sub("<redacted-password>", text)
    text = DEMO_EMAIL_RE.sub("<redacted-demo-email>", text)
    return text


def sanitize_obj(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                sanitized[key] = item if isinstance(item, bool) else "<redacted>"
            else:
                sanitized[key] = sanitize_obj(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_obj(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(sanitize_obj(row), ensure_ascii=False) + "\n")


def ensure_dirs(output: Path) -> None:
    for child in ("screenshots", "dom_snapshots"):
        (output / child).mkdir(parents=True, exist_ok=True)


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
    driver = webdriver.Chrome(options=options)
    try:
        driver.execute_cdp_cmd("Network.enable", {})
    except WebDriverException:
        pass
    return driver


def clear_browser_logs(driver: webdriver.Chrome) -> None:
    for log_type in ("browser", "performance"):
        try:
            driver.get_log(log_type)
        except WebDriverException:
            continue


class NetworkRecorder:
    def __init__(self, driver: webdriver.Chrome) -> None:
        self.driver = driver
        self.events: list[dict[str, Any]] = []
        self.request_urls: dict[str, str] = {}

    def poll(self, mode: str, scenario: str) -> list[dict[str, Any]]:
        try:
            logs = self.driver.get_log("performance")
        except WebDriverException:
            return []
        parsed: list[dict[str, Any]] = []
        for entry in logs:
            try:
                message = json.loads(entry.get("message", "{}")).get("message", {})
            except json.JSONDecodeError:
                continue
            event = self._parse(message, mode, scenario)
            if event:
                parsed.append(event)
        self.events.extend(parsed)
        return parsed

    def _parse(self, message: dict[str, Any], mode: str, scenario: str) -> dict[str, Any] | None:
        method = message.get("method")
        params = message.get("params", {})
        base = {
            "timestamp": utc_iso(),
            "mode": mode,
            "scenario": scenario,
            "cdp_method": method,
            "request_id": params.get("requestId", ""),
        }
        if method == "Network.requestWillBeSent":
            request = params.get("request", {})
            url = request.get("url", "")
            if not url:
                return None
            self.request_urls[str(params.get("requestId", ""))] = sanitize_text(url)
            return {
                **base,
                "event": "request",
                "url": sanitize_text(url),
                "method": request.get("method", ""),
                "resource_type": params.get("type", ""),
                "initiator_type": (params.get("initiator") or {}).get("type", ""),
            }
        if method == "Network.responseReceived":
            response = params.get("response", {})
            url = response.get("url", "")
            if not url:
                return None
            return {
                **base,
                "event": "response",
                "url": sanitize_text(url),
                "status": int(response.get("status") or 0),
                "mime_type": response.get("mimeType", ""),
                "from_disk_cache": bool(response.get("fromDiskCache")),
                "from_service_worker": bool(response.get("fromServiceWorker")),
            }
        if method == "Network.loadingFailed":
            request_id = str(params.get("requestId", ""))
            return {
                **base,
                "event": "loading_failed",
                "url": self.request_urls.get(request_id, ""),
                "error_text": sanitize_text(params.get("errorText", "")),
                "canceled": bool(params.get("canceled")),
                "resource_type": params.get("type", ""),
            }
        return None


class ConsoleRecorder:
    def __init__(self, driver: webdriver.Chrome) -> None:
        self.driver = driver
        self.rows: list[dict[str, Any]] = []

    def poll(self, mode: str, scenario: str) -> list[dict[str, Any]]:
        try:
            logs = self.driver.get_log("browser")
        except WebDriverException:
            return []
        rows = [
            {
                "timestamp": utc_iso(),
                "mode": mode,
                "scenario": scenario,
                "level": log.get("level", ""),
                "message": sanitize_text(log.get("message", "")),
            }
            for log in logs
        ]
        self.rows.extend(rows)
        return rows


def collect_ui_state(driver: WebDriver) -> dict[str, Any]:
    state = {
        "url": "",
        "title": "",
        "body_text_length": 0,
        "timeout_texts": [],
        "retry_texts": [],
        "alert_texts": [],
        "job_link_count": 0,
        "recommendation_like_card_count": 0,
        "loading_text_present": False,
        "spinner_like_count": 0,
        "theme": {},
    }
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        text = body.text or ""
        state["url"] = sanitize_text(driver.current_url)
        state["title"] = sanitize_text(driver.title)
        state["body_text_length"] = len(text.strip())
        state["timeout_texts"] = [item for item in TIMEOUT_TEXTS if item in text]
        state["retry_texts"] = [item for item in RETRY_TEXTS if item in text]
        alerts = []
        for alert in driver.find_elements(By.CSS_SELECTOR, "[role='alert']"):
            if alert.text.strip():
                alerts.append(sanitize_text(alert.text.strip()[:300]))
        state["alert_texts"] = alerts[:8]
        state["job_link_count"] = len(driver.find_elements(By.CSS_SELECTOR, "a[href^='/jobs/']"))
        state["recommendation_like_card_count"] = len(
            driver.find_elements(By.XPATH, "//*[contains(., '% Match')]")
        )
        state["loading_text_present"] = "Memuat" in text or "Memproses" in text
        state["spinner_like_count"] = len(
            driver.find_elements(By.CSS_SELECTOR, ".animate-spin,[role='status']")
        )
        state["theme"] = driver.execute_script(
            """
            return {
              dataTheme: document.documentElement.getAttribute('data-theme'),
              colorScheme: document.documentElement.style.colorScheme || '',
              storedTheme: localStorage.getItem('scpa_theme')
            };
            """
        )
    except WebDriverException as exc:
        state["inspection_error"] = sanitize_text(str(exc)[:300])
    return state


def capture_artifacts(driver: WebDriver, output: Path, mode: str, scenario: str, label: str) -> tuple[str, str]:
    base = f"{safe_name(mode)}_{safe_name(scenario)}_{safe_name(label)}"
    screenshot = output / "screenshots" / f"{base}.png"
    dom = output / "dom_snapshots" / f"{base}.html"
    try:
        driver.save_screenshot(str(screenshot))
    except WebDriverException:
        pass
    try:
        html = driver.execute_script("return document.documentElement.outerHTML") or ""
        dom.write_text(sanitize_text(html), encoding="utf-8")
    except WebDriverException:
        pass
    return rel(screenshot), rel(dom)


def wait_for_ready(driver: WebDriver, timeout: int = 30) -> None:
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") in {"interactive", "complete"}
    )


def set_react_input_value(driver: WebDriver, selector: str, value: str) -> None:
    driver.execute_script(
        """
        const input = document.querySelector(arguments[0]);
        if (!input) throw new Error(`Input not found: ${arguments[0]}`);
        const setter = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype,
          'value'
        ).set;
        setter.call(input, arguments[1]);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        selector,
        value,
    )


def set_network_throttle(
    driver: webdriver.Chrome,
    latency_ms: int,
    download_bytes_per_second: int,
    upload_bytes_per_second: int,
) -> bool:
    try:
        driver.execute_cdp_cmd(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": latency_ms,
                "downloadThroughput": download_bytes_per_second,
                "uploadThroughput": upload_bytes_per_second,
                "connectionType": "cellular3g",
            },
        )
        return True
    except WebDriverException:
        return False


def reset_network_throttle(driver: webdriver.Chrome) -> None:
    try:
        driver.execute_cdp_cmd(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": 0,
                "downloadThroughput": -1,
                "uploadThroughput": -1,
                "connectionType": "none",
            },
        )
    except WebDriverException:
        pass


def wait_for_endpoint(
    recorder: NetworkRecorder,
    mode: str,
    scenario: str,
    endpoint_fragment: str,
    timeout: float,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    seen: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        events = recorder.poll(mode, scenario)
        seen.extend(
            event
            for event in events
            if endpoint_fragment in event.get("url", "")
        )
        if any(event.get("event") in {"response", "loading_failed"} for event in seen):
            return seen
        time.sleep(0.25)
    return seen


def perform_login(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    console: ConsoleRecorder,
    base_url: str,
    mode: str,
    email: str | None,
    password: str | None,
) -> dict[str, Any]:
    result = {"attempted": bool(email and password), "success": False, "has_token": False}
    if not email or not password:
        return result
    clear_browser_logs(driver)
    driver.get(f"{base_url.rstrip('/')}/auth")
    wait_for_ready(driver)
    try:
        WebDriverWait(driver, 25).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "input[name='email']")
            and d.find_elements(By.CSS_SELECTOR, "input[name='password']")
            and d.find_elements(By.CSS_SELECTOR, "button[type='submit']")
        )
        set_react_input_value(driver, "input[name='email']", email)
        set_react_input_value(driver, "input[name='password']", password)
        button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].scrollIntoView({ block: 'center' });", button)
        driver.execute_script("arguments[0].click();", button)
        WebDriverWait(driver, 25).until(
            lambda d: bool(d.execute_script("return localStorage.getItem('scpa_token')"))
        )
        result["success"] = True
    except (TimeoutException, WebDriverException) as exc:
        result["error"] = sanitize_text(str(exc)[:300])
    finally:
        recorder.poll(mode, "login")
        console.poll(mode, "login")
        result["has_token"] = bool(
            driver.execute_script("return Boolean(localStorage.getItem('scpa_token'))")
        )
        result["login_request_count"] = count_matching(recorder.events, "/api/auth/login", "request")
    return result


def add_check(
    scenario: ScenarioResult,
    bug_id: str,
    name: str,
    passed: bool,
    severity: str = "p1",
    **evidence: Any,
) -> None:
    scenario.checks.append(
        CheckResult(
            bug_id=bug_id,
            name=name,
            passed=passed,
            severity=severity,
            evidence=sanitize_obj(evidence),
        )
    )


def count_matching(events: list[dict[str, Any]], fragment: str, event_type: str | None = None) -> int:
    return sum(
        1
        for event in events
        if fragment in event.get("url", "")
        and (event_type is None or event.get("event") == event_type)
    )


def canceled_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event.get("event") == "loading_failed"
        and (
            event.get("canceled")
            or "cancel" in str(event.get("error_text", "")).lower()
            or "abort" in str(event.get("error_text", "")).lower()
        )
    ]


def audit_jobs(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    console: ConsoleRecorder,
    output: Path,
    mode: str,
    base_url: str,
    route: str,
    settle: float,
) -> ScenarioResult:
    scenario = ScenarioResult(mode=mode, name="jobs", route=route)
    clear_browser_logs(driver)
    driver.get(f"{base_url.rstrip('/')}{route}")
    wait_for_ready(driver)
    wait_for_endpoint(recorder, mode, "jobs", "/api/jobs", 30)
    time.sleep(settle)
    events_after_load = recorder.poll(mode, "jobs")
    console.poll(mode, "jobs")
    shot, dom = capture_artifacts(driver, output, mode, "jobs", "initial")
    scenario.screenshots.append(shot)
    scenario.dom_snapshots.append(dom)
    state = collect_ui_state(driver)
    scenario.final_ui_state = state
    all_events = [event for event in recorder.events if event.get("mode") == mode and event.get("scenario") == "jobs"]
    scenario.network_event_count = len(all_events)
    scenario.canceled_request_count = len(canceled_events(all_events))

    successful_jobs_response = any(
        event.get("event") == "response"
        and "/api/jobs" in event.get("url", "")
        and int(event.get("status") or 0) < 400
        for event in all_events
    )
    add_check(
        scenario,
        "BUG-RUNTIME-JOBS-TIMEOUT",
        "no false timeout after jobs response",
        not (successful_jobs_response and state["timeout_texts"]),
        successful_jobs_response=successful_jobs_response,
        timeout_texts=state["timeout_texts"],
    )
    add_check(
        scenario,
        "BUG-RUNTIME-JOBS-TIMEOUT",
        "job cards render when jobs response succeeds",
        (not successful_jobs_response) or state["job_link_count"] > 0,
        successful_jobs_response=successful_jobs_response,
        job_link_count=state["job_link_count"],
    )
    add_check(
        scenario,
        "BUG-RUNTIME-CANCELED-FETCH-SYSTEMIC",
        "canceled jobs requests do not leave final timeout UI",
        not (scenario.canceled_request_count and state["timeout_texts"]),
        canceled_request_count=scenario.canceled_request_count,
        timeout_texts=state["timeout_texts"],
    )

    try:
        location = driver.find_element(By.CSS_SELECTOR, "#loc")
        location.clear()
        location.send_keys("Jakarta")
        exp = Select(driver.find_element(By.CSS_SELECTOR, "#exp"))
        exp.select_by_value("entry")
        driver.find_element(By.XPATH, "//button[contains(., 'Filter')]").click()
        wait_for_endpoint(recorder, mode, "jobs_filter", "/api/jobs", 20)
        time.sleep(settle)
        recorder.poll(mode, "jobs_filter")
        console.poll(mode, "jobs_filter")
        shot, dom = capture_artifacts(driver, output, mode, "jobs", "filter")
        scenario.screenshots.append(shot)
        scenario.dom_snapshots.append(dom)
        filter_state = collect_ui_state(driver)
        add_check(
            scenario,
            "BUG-RUNTIME-JOBS-TIMEOUT",
            "filter action does not show stale timeout",
            not filter_state["timeout_texts"],
            timeout_texts=filter_state["timeout_texts"],
            retry_texts=filter_state["retry_texts"],
        )
    except WebDriverException as exc:
        scenario.notes.append(f"filter action skipped: {sanitize_text(str(exc)[:240])}")

    if events_after_load:
        scenario.notes.append(f"captured {len(events_after_load)} post-load network events")
    scenario.status = "passed" if all(check.passed for check in scenario.checks) else "failed"
    return scenario


def audit_recommendations(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    console: ConsoleRecorder,
    output: Path,
    mode: str,
    base_url: str,
    settle: float,
    exercise_actions: bool,
) -> ScenarioResult:
    scenario = ScenarioResult(mode=mode, name="recommendations", route="/recommendations")
    clear_browser_logs(driver)
    driver.get(f"{base_url.rstrip('/')}/recommendations")
    wait_for_ready(driver)
    for endpoint in ("/api/recommendations", "/api/jobs/saved", "/api/applications", "/api/learning-path", "/api/auth/me"):
        wait_for_endpoint(recorder, mode, "recommendations", endpoint, 3)
    time.sleep(settle)
    recorder.poll(mode, "recommendations")
    console.poll(mode, "recommendations")
    shot, dom = capture_artifacts(driver, output, mode, "recommendations", "initial")
    scenario.screenshots.append(shot)
    scenario.dom_snapshots.append(dom)
    state = collect_ui_state(driver)
    scenario.final_ui_state = state
    all_events = [
        event
        for event in recorder.events
        if event.get("mode") == mode and event.get("scenario") == "recommendations"
    ]
    scenario.network_event_count = len(all_events)
    scenario.canceled_request_count = len(canceled_events(all_events))
    scenario.auth_me_count = count_matching(all_events, "/api/auth/me", "request")

    successful_recs_response = any(
        event.get("event") == "response"
        and "/api/recommendations" in event.get("url", "")
        and int(event.get("status") or 0) < 400
        for event in all_events
    )
    add_check(
        scenario,
        "BUG-RUNTIME-RECOMMENDATIONS-TIMEOUT",
        "no false timeout after recommendations response",
        not (successful_recs_response and state["timeout_texts"]),
        successful_recs_response=successful_recs_response,
        timeout_texts=state["timeout_texts"],
    )
    add_check(
        scenario,
        "BUG-RUNTIME-RECOMMENDATIONS-TIMEOUT",
        "recommendation cards render when response succeeds",
        (not successful_recs_response) or state["recommendation_like_card_count"] > 0,
        successful_recs_response=successful_recs_response,
        recommendation_like_card_count=state["recommendation_like_card_count"],
    )
    add_check(
        scenario,
        "BUG-RUNTIME-CANCELED-FETCH-SYSTEMIC",
        "canceled recommendation requests do not leave final timeout UI",
        not (scenario.canceled_request_count and state["timeout_texts"]),
        canceled_request_count=scenario.canceled_request_count,
        timeout_texts=state["timeout_texts"],
    )

    before_sort_reqs = count_matching(recorder.events, "/api/recommendations", "request")
    try:
        selects = driver.find_elements(By.TAG_NAME, "select")
        if selects:
            Select(selects[0]).select_by_value("semantic_fit")
            time.sleep(1.0)
            recorder.poll(mode, "recommendations_sort")
            console.poll(mode, "recommendations_sort")
            after_sort_reqs = count_matching(recorder.events, "/api/recommendations", "request")
            add_check(
                scenario,
                "BUG-RUNTIME-RECOMMENDATIONS-TIMEOUT",
                "sort dropdown does not create refetch storm",
                after_sort_reqs - before_sort_reqs <= 1,
                before_sort_reqs=before_sort_reqs,
                after_sort_reqs=after_sort_reqs,
            )
    except WebDriverException as exc:
        scenario.notes.append(f"sort check skipped: {sanitize_text(str(exc)[:240])}")

    if exercise_actions:
        try:
            save_buttons = [
                button
                for button in driver.find_elements(By.TAG_NAME, "button")
                if "Simpan" in button.text or "Tersimpan" in button.text
            ]
            if save_buttons:
                save_buttons[0].click()
                time.sleep(1.5)
                recorder.poll(mode, "recommendations_save")
                console.poll(mode, "recommendations_save")
                action_state = collect_ui_state(driver)
                add_check(
                    scenario,
                    "BUG-RUNTIME-SAVED-REQUEST-CANCEL",
                    "save action does not trigger final timeout UI",
                    not action_state["timeout_texts"],
                    timeout_texts=action_state["timeout_texts"],
                    retry_texts=action_state["retry_texts"],
                )
        except WebDriverException as exc:
            scenario.notes.append(f"save action skipped: {sanitize_text(str(exc)[:240])}")
    else:
        scenario.notes.append("save/skip mutation disabled; run with --exercise-actions to mutate demo state")

    scenario.status = "passed" if all(check.passed for check in scenario.checks) else "failed"
    return scenario


def audit_jobs_cancellation(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    console: ConsoleRecorder,
    output: Path,
    mode: str,
    base_url: str,
    route: str,
    settle: float,
) -> ScenarioResult:
    scenario = ScenarioResult(mode=mode, name="jobs_cancellation", route=route)
    clear_browser_logs(driver)
    driver.get(f"{base_url.rstrip('/')}{route}")
    wait_for_ready(driver)
    wait_for_endpoint(recorder, mode, "jobs_cancellation", "/api/jobs", 20)
    throttle_enabled = set_network_throttle(driver, 2500, 24_000, 12_000)
    scenario.notes.append(f"network throttle enabled={throttle_enabled}")
    try:
        for city, experience in (("Jakarta", "entry"), ("Bandung", "mid"), ("Surabaya", "senior")):
            location = WebDriverWait(driver, 15).until(
                lambda d: d.find_element(By.CSS_SELECTOR, "#loc")
            )
            location.clear()
            location.send_keys(city)
            try:
                Select(driver.find_element(By.CSS_SELECTOR, "#exp")).select_by_value(experience)
            except WebDriverException:
                pass
            button = driver.find_element(By.XPATH, "//button[contains(., 'Filter')]")
            driver.execute_script("arguments[0].click();", button)
            time.sleep(0.2)
    except WebDriverException as exc:
        scenario.notes.append(f"targeted jobs cancellation action failed: {sanitize_text(str(exc)[:240])}")
    finally:
        reset_network_throttle(driver)

    wait_for_endpoint(recorder, mode, "jobs_cancellation", "/api/jobs", 35)
    time.sleep(settle)
    recorder.poll(mode, "jobs_cancellation")
    console.poll(mode, "jobs_cancellation")
    shot, dom = capture_artifacts(driver, output, mode, "jobs_cancellation", "final")
    scenario.screenshots.append(shot)
    scenario.dom_snapshots.append(dom)
    state = collect_ui_state(driver)
    scenario.final_ui_state = state
    all_events = [
        event
        for event in recorder.events
        if event.get("mode") == mode and event.get("scenario") == "jobs_cancellation"
    ]
    canceled = canceled_events(all_events)
    scenario.network_event_count = len(all_events)
    scenario.canceled_request_count = len(canceled)
    successful_jobs_response = any(
        event.get("event") == "response"
        and "/api/jobs" in event.get("url", "")
        and int(event.get("status") or 0) < 400
        for event in all_events
    )
    add_check(
        scenario,
        "BUG-RUNTIME-CANCELED-FETCH-SYSTEMIC",
        "targeted jobs filter scenario captures cancellation signal",
        bool(canceled),
        canceled_request_count=len(canceled),
        canceled_urls=[event.get("url", "") for event in canceled[:8]],
        throttle_enabled=throttle_enabled,
    )
    add_check(
        scenario,
        "BUG-RUNTIME-JOBS-TIMEOUT",
        "targeted jobs cancellation does not leave false timeout after current success",
        not (successful_jobs_response and state["timeout_texts"]),
        successful_jobs_response=successful_jobs_response,
        timeout_texts=state["timeout_texts"],
        retry_texts=state["retry_texts"],
    )
    scenario.status = "passed" if all(check.passed for check in scenario.checks) else "failed"
    return scenario


def navigate_without_wait(driver: webdriver.Chrome, url: str) -> None:
    try:
        driver.execute_script("window.location.assign(arguments[0]);", url)
    except WebDriverException:
        driver.get(url)


def audit_recommendations_cancellation(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    console: ConsoleRecorder,
    output: Path,
    mode: str,
    base_url: str,
    settle: float,
) -> ScenarioResult:
    scenario = ScenarioResult(mode=mode, name="recommendations_cancellation", route="/recommendations")
    clear_browser_logs(driver)
    driver.get(f"{base_url.rstrip('/')}/dashboard")
    wait_for_ready(driver)
    throttle_enabled = set_network_throttle(driver, 2500, 24_000, 12_000)
    scenario.notes.append(f"network throttle enabled={throttle_enabled}")
    try:
        for refresh in ("runtime-audit-1", "runtime-audit-2", "runtime-audit-3"):
            navigate_without_wait(
                driver,
                f"{base_url.rstrip('/')}/recommendations?refresh={refresh}",
            )
            time.sleep(0.35)
    finally:
        reset_network_throttle(driver)

    wait_for_ready(driver, 35)
    wait_for_endpoint(recorder, mode, "recommendations_cancellation", "/api/recommendations", 40)
    time.sleep(settle)
    recorder.poll(mode, "recommendations_cancellation")
    console.poll(mode, "recommendations_cancellation")
    shot, dom = capture_artifacts(driver, output, mode, "recommendations_cancellation", "final")
    scenario.screenshots.append(shot)
    scenario.dom_snapshots.append(dom)
    state = collect_ui_state(driver)
    scenario.final_ui_state = state
    all_events = [
        event
        for event in recorder.events
        if event.get("mode") == mode and event.get("scenario") == "recommendations_cancellation"
    ]
    canceled = canceled_events(all_events)
    scenario.network_event_count = len(all_events)
    scenario.canceled_request_count = len(canceled)
    successful_recs_response = any(
        event.get("event") == "response"
        and "/api/recommendations" in event.get("url", "")
        and int(event.get("status") or 0) < 400
        for event in all_events
    )
    add_check(
        scenario,
        "BUG-RUNTIME-CANCELED-FETCH-SYSTEMIC",
        "targeted recommendations navigation scenario captures cancellation signal",
        bool(canceled),
        canceled_request_count=len(canceled),
        canceled_urls=[event.get("url", "") for event in canceled[:8]],
        throttle_enabled=throttle_enabled,
    )
    add_check(
        scenario,
        "BUG-RUNTIME-RECOMMENDATIONS-TIMEOUT",
        "targeted recommendations cancellation does not leave false timeout after current success",
        not (successful_recs_response and state["timeout_texts"]),
        successful_recs_response=successful_recs_response,
        timeout_texts=state["timeout_texts"],
        retry_texts=state["retry_texts"],
    )
    scenario.status = "passed" if all(check.passed for check in scenario.checks) else "failed"
    return scenario


def audit_auth_navigation(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    console: ConsoleRecorder,
    output: Path,
    mode: str,
    base_url: str,
    settle: float,
) -> ScenarioResult:
    scenario = ScenarioResult(mode=mode, name="auth_session", route="/dashboard,/profile,/recommendations,/analytics")
    clear_browser_logs(driver)
    routes = ["/dashboard", "/profile", "/recommendations", "/analytics"]
    for route in routes:
        driver.get(f"{base_url.rstrip('/')}{route}")
        wait_for_ready(driver)
        time.sleep(0.6)
        recorder.poll(mode, "auth_session")
    time.sleep(settle)
    console.poll(mode, "auth_session")
    shot, dom = capture_artifacts(driver, output, mode, "auth_session", "after_navigation")
    scenario.screenshots.append(shot)
    scenario.dom_snapshots.append(dom)
    state = collect_ui_state(driver)
    scenario.final_ui_state = state
    all_events = [
        event
        for event in recorder.events
        if event.get("mode") == mode and event.get("scenario") == "auth_session"
    ]
    scenario.network_event_count = len(all_events)
    scenario.canceled_request_count = len(canceled_events(all_events))
    scenario.auth_me_count = count_matching(all_events, "/api/auth/me", "request")
    add_check(
        scenario,
        "BUG-RUNTIME-AUTH-ME-REPEAT",
        "auth/me request count stays bounded during fast navigation",
        scenario.auth_me_count <= len(routes) + 1,
        auth_me_count=scenario.auth_me_count,
        route_count=len(routes),
    )
    add_check(
        scenario,
        "BUG-RUNTIME-CANCELED-FETCH-SYSTEMIC",
        "fast navigation does not leave persistent timeout UI",
        not state["timeout_texts"],
        timeout_texts=state["timeout_texts"],
    )
    scenario.status = "passed" if all(check.passed for check in scenario.checks) else "failed"
    return scenario


def audit_theme(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    console: ConsoleRecorder,
    output: Path,
    mode: str,
    base_url: str,
    settle: float,
) -> ScenarioResult:
    scenario = ScenarioResult(mode=mode, name="theme_toggle", route="/dashboard")
    clear_browser_logs(driver)
    driver.get(f"{base_url.rstrip('/')}/dashboard")
    wait_for_ready(driver)
    try:
        WebDriverWait(driver, 25).until(lambda d: d.find_elements(By.XPATH, THEME_BUTTON_XPATH))
        time.sleep(settle)
        shot, dom = capture_artifacts(driver, output, mode, "theme_toggle", "before")
        scenario.screenshots.append(shot)
        scenario.dom_snapshots.append(dom)
        before = collect_ui_state(driver)
        for _ in range(5):
            toggle = WebDriverWait(driver, 10).until(
                lambda d: d.find_element(By.XPATH, THEME_BUTTON_XPATH)
            )
            driver.execute_script("arguments[0].click();", toggle)
            time.sleep(0.2)
        time.sleep(settle)
        after = collect_ui_state(driver)
        shot, dom = capture_artifacts(driver, output, mode, "theme_toggle", "after_clicks")
        scenario.screenshots.append(shot)
        scenario.dom_snapshots.append(dom)
        driver.refresh()
        wait_for_ready(driver)
        time.sleep(settle)
        reload_state = collect_ui_state(driver)
        shot, dom = capture_artifacts(driver, output, mode, "theme_toggle", "after_reload")
        scenario.screenshots.append(shot)
        scenario.dom_snapshots.append(dom)
        console_rows = console.poll(mode, "theme_toggle")
        hydration_warnings = [
            row for row in console_rows if "hydration" in row.get("message", "").lower()
        ]
        scenario.final_ui_state = {
            "before": before,
            "after": after,
            "after_reload": reload_state,
            "hydration_warning_count": len(hydration_warnings),
        }
        add_check(
            scenario,
            "BUG-FE-THEME-TOGGLE-STUCK",
            "theme toggle has no stuck loading indicator after repeated clicks",
            after["spinner_like_count"] == 0 and not after["loading_text_present"],
            spinner_like_count=after["spinner_like_count"],
            loading_text_present=after["loading_text_present"],
        )
        add_check(
            scenario,
            "BUG-FE-THEME-TOGGLE-STUCK",
            "theme persists after reload",
            reload_state["theme"].get("storedTheme") in {"light", "dark"}
            and reload_state["theme"].get("dataTheme") == reload_state["theme"].get("storedTheme"),
            after_theme=after["theme"],
            after_reload_theme=reload_state["theme"],
        )
        add_check(
            scenario,
            "BUG-FE-THEME-TOGGLE-STUCK",
            "no hydration warning during theme toggle scenario",
            len(hydration_warnings) == 0,
            hydration_warning_count=len(hydration_warnings),
        )
    except WebDriverException as exc:
        scenario.notes.append(f"theme toggle not found or failed: {sanitize_text(str(exc)[:240])}")
        add_check(
            scenario,
            "BUG-FE-THEME-TOGGLE-STUCK",
            "theme toggle is discoverable",
            False,
            error=sanitize_text(str(exc)[:240]),
        )
    recorder.poll(mode, "theme_toggle")
    scenario.status = "passed" if all(check.passed for check in scenario.checks) else "failed"
    return scenario


def wait_gateway_health(api_base: str, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    url = f"{api_base.rstrip('/')}/health"
    while time.monotonic() < deadline:
        try:
            with urlopen(Request(url), timeout=4) as response:  # noqa: S310 - local debug target
                if int(response.status) == 200:
                    return True
        except (OSError, URLError):
            time.sleep(1)
    return False


def restart_gateway(service: str) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(
        ["docker", "compose", "restart", service],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "returncode": proc.returncode,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "stdout": sanitize_text(proc.stdout[-1000:]),
        "stderr": sanitize_text(proc.stderr[-1000:]),
    }


def audit_gateway_restart(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    console: ConsoleRecorder,
    output: Path,
    mode: str,
    base_url: str,
    api_base: str,
    settle: float,
    service: str,
) -> ScenarioResult:
    scenario = ScenarioResult(mode=mode, name="gateway_restart", route="/analytics")
    clear_browser_logs(driver)
    driver.get(f"{base_url.rstrip('/')}/analytics")
    wait_for_ready(driver)
    time.sleep(settle)
    before = collect_ui_state(driver)
    shot, dom = capture_artifacts(driver, output, mode, "gateway_restart", "before")
    scenario.screenshots.append(shot)
    scenario.dom_snapshots.append(dom)
    restart_info = restart_gateway(service)
    gateway_healthy = wait_gateway_health(api_base)
    driver.refresh()
    wait_for_ready(driver)
    wait_for_endpoint(recorder, mode, "gateway_restart", "/api/jobs", 35)
    time.sleep(settle)
    recorder.poll(mode, "gateway_restart")
    console.poll(mode, "gateway_restart")
    after = collect_ui_state(driver)
    shot, dom = capture_artifacts(driver, output, mode, "gateway_restart", "after")
    scenario.screenshots.append(shot)
    scenario.dom_snapshots.append(dom)
    scenario.final_ui_state = {"before": before, "after": after, "restart": restart_info}
    all_events = [
        event
        for event in recorder.events
        if event.get("mode") == mode and event.get("scenario") == "gateway_restart"
    ]
    scenario.network_event_count = len(all_events)
    scenario.canceled_request_count = len(canceled_events(all_events))
    add_check(
        scenario,
        "BUG-RUNTIME-CANCELED-FETCH-SYSTEMIC",
        "gateway becomes healthy after restart",
        gateway_healthy and restart_info["returncode"] == 0,
        gateway_healthy=gateway_healthy,
        restart_returncode=restart_info["returncode"],
    )
    add_check(
        scenario,
        "BUG-RUNTIME-JOBS-TIMEOUT",
        "gateway restart does not leave permanent jobs timeout UI",
        not after["timeout_texts"],
        timeout_texts=after["timeout_texts"],
        retry_texts=after["retry_texts"],
    )
    scenario.status = "passed" if all(check.passed for check in scenario.checks) else "failed"
    return scenario


def collect_gateway_logs(service: str, tail: int) -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["docker", "compose", "logs", "--no-color", "--tail", str(tail), service],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    rows = []
    for line in proc.stdout.splitlines()[-tail:]:
        rows.append({"timestamp": utc_iso(), "service": service, "line": sanitize_text(line)})
    if proc.stderr.strip():
        rows.append({"timestamp": utc_iso(), "service": service, "stderr": sanitize_text(proc.stderr[-1000:])})
    return rows


def run_mode(
    driver: webdriver.Chrome,
    output: Path,
    mode: str,
    base_url: str,
    api_base: str,
    email: str | None,
    password: str | None,
    args: argparse.Namespace,
) -> tuple[list[ScenarioResult], NetworkRecorder, ConsoleRecorder, dict[str, Any]]:
    recorder = NetworkRecorder(driver)
    console = ConsoleRecorder(driver)
    driver.get(base_url.rstrip("/"))
    wait_for_ready(driver)
    driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    auth_result = perform_login(driver, recorder, console, base_url, mode, email, password)
    scenarios: list[ScenarioResult] = []
    if not auth_result.get("success"):
        failure = ScenarioResult(mode=mode, name="login", route="/auth", status="blocked")
        failure.notes.append("authenticated runtime scenarios require successful login")
        shot, dom = capture_artifacts(driver, output, mode, "login", "blocked")
        failure.screenshots.append(shot)
        failure.dom_snapshots.append(dom)
        scenarios.append(failure)
        return scenarios, recorder, console, auth_result

    scenarios.append(
        audit_jobs(driver, recorder, console, output, mode, base_url, args.jobs_route, args.settle_seconds)
    )
    scenarios.append(
        audit_recommendations(
            driver,
            recorder,
            console,
            output,
            mode,
            base_url,
            args.settle_seconds,
            args.exercise_actions,
        )
    )
    if not args.skip_cancellation_scenarios:
        scenarios.append(
            audit_jobs_cancellation(
                driver,
                recorder,
                console,
                output,
                mode,
                base_url,
                args.jobs_route,
                args.settle_seconds,
            )
        )
        scenarios.append(
            audit_recommendations_cancellation(
                driver,
                recorder,
                console,
                output,
                mode,
                base_url,
                args.settle_seconds,
            )
        )
    scenarios.append(
        audit_auth_navigation(driver, recorder, console, output, mode, base_url, args.settle_seconds)
    )
    scenarios.append(
        audit_theme(driver, recorder, console, output, mode, base_url, args.settle_seconds)
    )
    if args.restart_gateway:
        scenarios.append(
            audit_gateway_restart(
                driver,
                recorder,
                console,
                output,
                mode,
                base_url,
                api_base,
                args.settle_seconds,
                args.gateway_service,
            )
        )
    return scenarios, recorder, console, auth_result


def report_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Runtime Contract Audit Report",
        "",
        f"Generated: {summary['generated_at']}",
        f"Gateway: `{summary['api_base']}`",
        "",
        "## Summary",
        f"- Modes requested: {', '.join(summary['modes_requested'])}",
        f"- Scenarios: {summary['scenario_count']}",
        f"- Failed checks: {summary['failed_check_count']}",
        f"- Canceled request events: {summary['canceled_request_count']}",
        f"- Console severe entries: {summary['console_severe_count']}",
        "",
        "## Mode Results",
    ]
    for mode in summary["modes"]:
        lines.append(f"- `{mode['mode']}` at `{mode['base_url']}`: login success={mode['auth'].get('success')}, has token={mode['auth'].get('has_token')}")
        for scenario in mode["scenarios"]:
            failed = [check for check in scenario["checks"] if not check["passed"]]
            lines.append(
                f"  - {scenario['name']}: {scenario['status']}, checks={len(scenario['checks'])}, failed={len(failed)}, canceled={scenario['canceled_request_count']}, auth/me={scenario['auth_me_count']}"
            )
            if scenario["notes"]:
                for note in scenario["notes"][:4]:
                    lines.append(f"    - note: {note}")
    lines.extend(
        [
            "",
            "## Artifact Locations",
            "- `reports/debug/runtime_contract/summary.json`",
            "- `reports/debug/runtime_contract/network.ndjson`",
            "- `reports/debug/runtime_contract/console.ndjson`",
            "- `reports/debug/runtime_contract/gateway_logs.ndjson`",
            "- `reports/debug/runtime_contract/screenshots/`",
            "- `reports/debug/runtime_contract/dom_snapshots/`",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SCPA runtime contract Selenium audit")
    parser.add_argument("--dev-url", default="http://localhost:3000")
    parser.add_argument("--prod-url", default="http://localhost:3001")
    parser.add_argument("--api-base", default="http://localhost:9000")
    parser.add_argument("--mode", choices=["dev", "prod", "both"], default="both")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--jobs-route", default="/analytics")
    parser.add_argument("--settle-seconds", type=float, default=2.5)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1100)
    parser.add_argument("--chrome-binary", default=None)
    parser.add_argument("--restart-gateway", action="store_true")
    parser.add_argument("--gateway-service", default="gateway")
    parser.add_argument("--gateway-log-tail", type=int, default=300)
    parser.add_argument("--exercise-actions", action="store_true")
    parser.add_argument("--skip-cancellation-scenarios", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_dirs(args.output)
    modes: list[tuple[str, str]] = []
    if args.mode in {"dev", "both"}:
        modes.append(("dev", args.dev_url))
    if args.mode in {"prod", "both"}:
        modes.append(("prod", args.prod_url))

    all_scenarios: list[ScenarioResult] = []
    all_network: list[dict[str, Any]] = []
    all_console: list[dict[str, Any]] = []
    mode_summaries: list[dict[str, Any]] = []

    driver = build_driver(args.headless, args.width, args.height, args.chrome_binary)
    try:
        for mode, base_url in modes:
            scenarios, network, console, auth = run_mode(
                driver,
                args.output,
                mode,
                base_url.rstrip("/"),
                args.api_base.rstrip("/"),
                args.email,
                args.password,
                args,
            )
            all_scenarios.extend(scenarios)
            all_network.extend(network.events)
            all_console.extend(console.rows)
            mode_summaries.append(
                {
                    "mode": mode,
                    "base_url": base_url,
                    "auth": auth,
                    "scenarios": [asdict(scenario) for scenario in scenarios],
                }
            )
    finally:
        driver.quit()

    gateway_logs = collect_gateway_logs(args.gateway_service, args.gateway_log_tail)
    write_ndjson(args.output / "network.ndjson", all_network)
    write_ndjson(args.output / "console.ndjson", all_console)
    write_ndjson(args.output / "gateway_logs.ndjson", gateway_logs)

    failed_checks = [
        check
        for scenario in all_scenarios
        for check in scenario.checks
        if not check.passed
    ]
    summary = {
        "generated_at": utc_iso(),
        "api_base": args.api_base.rstrip("/"),
        "modes_requested": [mode for mode, _ in modes],
        "scenario_count": len(all_scenarios),
        "failed_check_count": len(failed_checks),
        "canceled_request_count": len(canceled_events(all_network)),
        "console_severe_count": sum(1 for row in all_console if row.get("level") == "SEVERE"),
        "modes": mode_summaries,
    }
    (args.output / "summary.json").write_text(
        json.dumps(sanitize_obj(summary), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (args.output / "runtime_contract_report.md").write_text(
        report_markdown(sanitize_obj(summary)),
        encoding="utf-8",
    )
    return 0 if not failed_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
