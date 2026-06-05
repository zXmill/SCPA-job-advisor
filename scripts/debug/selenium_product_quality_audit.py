"""Semantic Selenium product-quality audit for SCPA.

This audit is stricter than the route-load smoke test. It checks whether key
frontend workflows behave correctly from a user perspective and writes durable
evidence under reports/debug/product_quality.

Secrets are intentionally not written to artifacts. Browser tokens are used
only inside the browser session and are never serialized.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "reports" / "debug" / "product_quality"

TIMEOUT_TEXTS = [
    "Permintaan kehabisan waktu. Coba lagi.",
    "Permintaan kehabisan waktu. Silakan coba lagi.",
    "Pencocokan AI memakan waktu terlalu lama. Coba lagi sebentar.",
]

RETRY_TEXTS = ["Coba Lagi", "Muat Ulang"]

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

SKILL_QUERIES = [
    "s",
    "sql",
    "machine",
    "data",
    "python",
    "docker",
    "kubernetes",
    "ml",
    "ai",
    "statistics",
    "credit",
    "airflow",
    "terraform",
    "english",
    "komunikasi",
    "analisis",
]


@dataclass
class CheckResult:
    bug_id: str
    check: str
    passed: bool
    severity: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditSection:
    name: str
    route: str
    checks: list[CheckResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    dom_snapshots: list[str] = field(default_factory=list)
    network_event_count: int = 0
    canceled_request_count: int = 0


def safe_name(value: str) -> str:
    cleaned = value.strip("/") or "home"
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", cleaned)[:120]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def ensure_output_dirs(output_dir: Path) -> None:
    for child in ("screenshots", "dom_snapshots"):
        (output_dir / child).mkdir(parents=True, exist_ok=True)


def write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def redact_text(value: str) -> str:
    return EMAIL_RE.sub("<redacted-email>", value)


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


def http_json(url: str, method: str = "GET", timeout: int = 20) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if method.upper() != "GET":
        data = b"{}"
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, method=method.upper(), headers=headers)
    try:
        with urlopen(req, timeout=timeout) as response:  # noqa: S310 - local/debug URL from CLI
            raw = response.read().decode("utf-8")
            return int(response.status), json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001 - audit records controlled failure shape
        return 0, {"error": type(exc).__name__, "message": str(exc)[:300]}


def first_jobs(api_base: str, limit: int = 5) -> tuple[int, list[dict[str, Any]], dict[str, Any]]:
    url = f"{api_base.rstrip('/')}/api/jobs?{urlencode({'page': 1, 'limit': limit})}"
    status, payload = http_json(url)
    jobs: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        value = payload.get("jobs") or payload.get("items") or payload.get("results") or payload.get("data")
        if isinstance(value, list):
            jobs = [item for item in value if isinstance(item, dict)]
    elif isinstance(payload, list):
        jobs = [item for item in payload if isinstance(item, dict)]
    return status, jobs, payload if isinstance(payload, dict) else {"raw_type": type(payload).__name__}


class NetworkRecorder:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        self.events: list[dict[str, Any]] = []
        self.all_events: list[dict[str, Any]] = []

    def clear(self) -> None:
        self.events.clear()
        for log_type in ("browser", "performance"):
            try:
                self.driver.get_log(log_type)
            except WebDriverException:
                continue

    def poll(self, context: str) -> list[dict[str, Any]]:
        new_events: list[dict[str, Any]] = []
        try:
            perf_logs = self.driver.get_log("performance")
        except WebDriverException:
            return []
        for entry in perf_logs:
            try:
                message = json.loads(entry.get("message", "{}")).get("message", {})
            except json.JSONDecodeError:
                continue
            method = message.get("method")
            params = message.get("params", {})
            event = self._parse_event(method, params, context)
            if event:
                new_events.append(event)
        self.events.extend(new_events)
        self.all_events.extend(new_events)
        return new_events

    def _parse_event(self, method: str, params: dict[str, Any], context: str) -> dict[str, Any] | None:
        base = {
            "timestamp": now_iso(),
            "context": context,
            "cdp_method": method,
            "request_id": params.get("requestId", ""),
        }
        if method == "Network.requestWillBeSent":
            request = params.get("request", {})
            url = request.get("url", "")
            if not url:
                return None
            return {
                **base,
                "event": "request",
                "url": url,
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
                "url": url,
                "status": int(response.get("status") or 0),
                "mime_type": response.get("mimeType", ""),
                "resource_type": params.get("type", ""),
            }
        if method == "Network.loadingFailed":
            error_text = params.get("errorText", "")
            return {
                **base,
                "event": "loadingFailed",
                "url": "",
                "resource_type": params.get("type", ""),
                "error_text": error_text,
                "canceled": bool(params.get("canceled")) or error_text == "net::ERR_ABORTED",
            }
        if method == "Network.loadingFinished":
            return {
                **base,
                "event": "loadingFinished",
                "url": "",
                "encoded_data_length": params.get("encodedDataLength"),
            }
        return None

    def wait_for_url(self, pattern: str, timeout: float, context: str) -> bool:
        compiled = re.compile(pattern)
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            events = self.poll(context)
            if any(compiled.search(event.get("url", "")) for event in events):
                return True
            time.sleep(0.25)
        self.poll(context)
        return any(compiled.search(event.get("url", "")) for event in self.events)


def collect_console(driver: webdriver.Chrome, context: str) -> list[dict[str, Any]]:
    try:
        logs = driver.get_log("browser")
    except WebDriverException:
        return []
    rows = []
    for log in logs:
        rows.append(
            {
                "timestamp": now_iso(),
                "context": context,
                "level": log.get("level", ""),
                "message": redact_text(str(log.get("message", ""))),
            }
        )
    return rows


def body_text(driver: WebDriver) -> str:
    try:
        return redact_text(driver.find_element(By.TAG_NAME, "body").text or "")
    except WebDriverException:
        return ""


def visible_timeout_texts(text: str) -> list[str]:
    return [item for item in TIMEOUT_TEXTS if item.lower() in text.lower()]


def visible_retry_texts(text: str) -> list[str]:
    return [item for item in RETRY_TEXTS if item.lower() in text.lower()]


def visible_loading_elements(driver: WebDriver) -> list[str]:
    script = """
    const nodes = Array.from(document.querySelectorAll('.animate-spin, .animate-pulse, [role="status"]'));
    return nodes
      .filter((node) => {
        const style = window.getComputedStyle(node);
        const rect = node.getBoundingClientRect();
        const hidden = style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0;
        const srOnly = node.classList && node.classList.contains('sr-only');
        return !hidden && !srOnly;
      })
      .slice(0, 20)
      .map((node) => ({
        tag: node.tagName,
        className: String(node.getAttribute('class') || '').slice(0, 160),
        text: String(node.textContent || '').trim().slice(0, 160)
      }));
    """
    try:
        return [json.dumps(item, ensure_ascii=False) for item in driver.execute_script(script)]
    except WebDriverException:
        return []


def capture_artifacts(driver: webdriver.Chrome, output_dir: Path, section: AuditSection, name: str) -> None:
    screenshot = output_dir / "screenshots" / f"{safe_name(name)}.png"
    dom = output_dir / "dom_snapshots" / f"{safe_name(name)}.md"
    try:
        driver.save_screenshot(str(screenshot))
        section.screenshots.append(rel(screenshot))
    except WebDriverException as exc:
        section.notes.append(f"screenshot failed for {name}: {str(exc)[:200]}")
    try:
        text = body_text(driver)
        current_url = redact_text(getattr(driver, "current_url", ""))
        title = redact_text(getattr(driver, "title", ""))
        dom.write_text(
            "\n".join(
                [
                    f"# DOM Snapshot: {name}",
                    "",
                    f"- URL: `{current_url}`",
                    f"- Title: `{title}`",
                    "",
                    "## Body Text",
                    "",
                    text,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        section.dom_snapshots.append(rel(dom))
    except WebDriverException as exc:
        section.notes.append(f"dom snapshot failed for {name}: {str(exc)[:200]}")


def add_check(
    section: AuditSection,
    bug_id: str,
    check: str,
    passed: bool,
    severity: str = "P1",
    evidence: dict[str, Any] | None = None,
) -> None:
    section.checks.append(
        CheckResult(
            bug_id=bug_id,
            check=check,
            passed=passed,
            severity=severity,
            evidence=evidence or {},
        )
    )


def perform_login(driver: WebDriver, base_url: str, email: str | None, password: str | None) -> dict[str, Any]:
    result = {
        "attempted": bool(email and password),
        "email": "<demo-email>" if email else None,
        "success": False,
        "has_token": False,
        "current_url": "",
        "error": "",
    }
    if not email or not password:
        return result
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
        WebDriverWait(driver, 25).until(
            lambda d: bool(d.execute_script("return localStorage.getItem('scpa_token')"))
            or "/dashboard" in d.current_url
            or "/onboarding" in d.current_url
        )
        result["current_url"] = driver.current_url
        result["has_token"] = bool(driver.execute_script("return localStorage.getItem('scpa_token')"))
        result["success"] = result["has_token"] or "/dashboard" in driver.current_url or "/onboarding" in driver.current_url
    except WebDriverException as exc:
        result["current_url"] = getattr(driver, "current_url", "")
        result["error"] = str(exc)[:500]
    return result


def assert_authenticated(section: AuditSection, auth: dict[str, Any]) -> bool:
    if not auth.get("attempted"):
        section.notes.append("No credentials supplied; authenticated semantic checks may redirect to /auth.")
        return False
    if not auth.get("success"):
        section.notes.append(f"Login failed: {auth.get('error', '')[:200]}")
        return False
    return True


def audit_jobs_page(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    base_url: str,
    api_base: str,
    output_dir: Path,
    settle_seconds: float,
) -> AuditSection:
    section = AuditSection(name="Job Vacancies", route="/analytics")
    api_status, api_jobs, api_payload = first_jobs(api_base, limit=25)

    recorder.clear()
    driver.get(f"{base_url.rstrip('/')}/analytics")
    try:
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState") in {"interactive", "complete"}
        )
    except TimeoutException:
        section.notes.append("document.readyState did not settle for /analytics")
    jobs_request_seen = recorder.wait_for_url(r"/api/jobs(\?|$)", 25, "jobs-page-load")
    time.sleep(settle_seconds)
    recorder.poll("jobs-page-load")
    capture_artifacts(driver, output_dir, section, "jobs_page_initial")

    text = body_text(driver)
    timeout_hits = visible_timeout_texts(text)
    retry_hits = visible_retry_texts(text)
    loading_hits = visible_loading_elements(driver)
    sample_titles = [str(job.get("title") or "") for job in api_jobs[:5] if job.get("title")]
    sample_companies = [str(job.get("company") or "") for job in api_jobs[:5] if job.get("company")]
    expected_job_text_found = any(item and item in text for item in sample_titles + sample_companies)
    job_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='/jobs/'], a[href*='/jobs/']")

    add_check(
        section,
        "BUG-FE-JOBS-TIMEOUT",
        "jobs API request observed",
        jobs_request_seen,
        evidence={"api_status": api_status},
    )
    add_check(
        section,
        "BUG-FE-JOBS-TIMEOUT",
        "no visible jobs timeout message after page settle",
        not timeout_hits,
        evidence={"timeout_texts": timeout_hits},
    )
    add_check(
        section,
        "BUG-FE-JOBS-TIMEOUT",
        "job cards render when API returns jobs",
        (not api_jobs) or expected_job_text_found or len(job_links) > 0,
        evidence={
            "api_job_count": len(api_jobs),
            "sample_titles": sample_titles[:3],
            "job_link_count": len(job_links),
            "api_payload_keys": sorted(api_payload.keys()),
        },
    )
    add_check(
        section,
        "BUG-FE-JOBS-TIMEOUT",
        "no stuck loading indicator remains after network settle",
        len(loading_hits) == 0,
        evidence={"loading_elements": loading_hits},
    )
    add_check(
        section,
        "BUG-FE-JOBS-TIMEOUT",
        "retry button is absent after successful page state",
        not retry_hits,
        evidence={"retry_texts": retry_hits},
    )

    # Filter action by location and experience.
    before_count = len(recorder.events)
    try:
        loc = driver.find_element(By.ID, "loc")
        exp = Select(driver.find_element(By.ID, "exp"))
        loc.clear()
        loc.send_keys("Jakarta")
        exp.select_by_value("entry")
        driver.find_element(By.XPATH, "//button[contains(., 'Filter')]").click()
        recorder.wait_for_url(r"/api/jobs(\?|$)", 20, "jobs-filter")
        time.sleep(settle_seconds)
        recorder.poll("jobs-filter")
        capture_artifacts(driver, output_dir, section, "jobs_page_filter")
        filter_text = body_text(driver)
        filter_timeout_hits = visible_timeout_texts(filter_text)
        add_check(
            section,
            "BUG-FE-CANCELED-FETCH-RACE",
            "filter action does not leave visible timeout state",
            not filter_timeout_hits,
            evidence={"timeout_texts": filter_timeout_hits},
        )
    except WebDriverException as exc:
        section.notes.append(f"filter interaction failed: {str(exc)[:300]}")
        add_check(
            section,
            "BUG-FE-CANCELED-FETCH-RACE",
            "filter action executed",
            False,
            evidence={"error": str(exc)[:300]},
        )

    filter_events = recorder.events[before_count:]
    classify_canceled(section, filter_events, "BUG-FE-CANCELED-FETCH-RACE", body_text(driver))
    section.network_event_count = len(recorder.events)
    section.canceled_request_count = sum(1 for event in recorder.events if event.get("canceled"))
    return section


def audit_recommendations_page(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    base_url: str,
    output_dir: Path,
    settle_seconds: float,
    mutating_actions: bool,
) -> AuditSection:
    section = AuditSection(name="Recommendations", route="/recommendations")
    recorder.clear()
    driver.get(f"{base_url.rstrip('/')}/recommendations")
    try:
        WebDriverWait(driver, 45).until(
            lambda d: d.execute_script("return document.readyState") in {"interactive", "complete"}
        )
    except TimeoutException:
        section.notes.append("document.readyState did not settle for /recommendations")

    request_patterns = {
        "recommendations": r"/api/recommendations",
        "applications": r"/api/applications",
        "learning_path": r"/api/learning-path",
        "auth_me": r"/api/auth/me",
        "saved_jobs": r"/api/(jobs|recommendations)/saved",
    }
    seen = {
        name: recorder.wait_for_url(pattern, 25 if name == "recommendations" else 8, f"recommendations-{name}")
        for name, pattern in request_patterns.items()
    }
    time.sleep(settle_seconds)
    recorder.poll("recommendations-page-load")
    capture_artifacts(driver, output_dir, section, "recommendations_initial")

    text = body_text(driver)
    timeout_hits = visible_timeout_texts(text)
    retry_hits = visible_retry_texts(text)
    recommendation_card_evidence = {
        "match_occurrences": len(re.findall(r"\b\d{1,3}% Match\b", text)),
        "detail_links": len(driver.find_elements(By.CSS_SELECTOR, "a[href^='/jobs/'], a[href*='/jobs/']")),
        "body_text_length": len(text),
    }
    cards_rendered = recommendation_card_evidence["match_occurrences"] > 0 or recommendation_card_evidence["detail_links"] > 0

    add_check(
        section,
        "BUG-FE-RECOMMENDATIONS-TIMEOUT",
        "recommendation-related requests observed",
        bool(seen.get("recommendations")),
        evidence=seen,
    )
    add_check(
        section,
        "BUG-FE-RECOMMENDATIONS-TIMEOUT",
        "no visible recommendation timeout message after settle",
        not timeout_hits,
        evidence={"timeout_texts": timeout_hits},
    )
    add_check(
        section,
        "BUG-FE-RECOMMENDATIONS-TIMEOUT",
        "recommendation cards or detail links render",
        cards_rendered,
        evidence=recommendation_card_evidence,
    )
    add_check(
        section,
        "BUG-FE-RECOMMENDATIONS-TIMEOUT",
        "retry text is absent after successful page state",
        not retry_hits,
        evidence={"retry_texts": retry_hits},
    )

    before_sort = len(recorder.events)
    try:
        select = Select(driver.find_element(By.TAG_NAME, "select"))
        current = select.first_selected_option.get_attribute("value")
        target = "semantic_fit" if current != "semantic_fit" else "interaction_fit"
        select.select_by_value(target)
        time.sleep(1.0)
        recorder.poll("recommendations-sort")
        after_sort_events = recorder.events[before_sort:]
        refetches = [
            event for event in after_sort_events
            if event.get("event") == "request" and "/api/recommendations" in event.get("url", "")
        ]
        add_check(
            section,
            "BUG-FE-CANCELED-FETCH-RACE",
            "sort change does not refetch recommendations",
            len(refetches) == 0,
            evidence={"recommendation_refetches_after_sort": len(refetches)},
        )
    except WebDriverException as exc:
        section.notes.append(f"sort interaction failed: {str(exc)[:300]}")
        add_check(
            section,
            "BUG-FE-CANCELED-FETCH-RACE",
            "sort interaction executed",
            False,
            evidence={"error": str(exc)[:300]},
        )

    if mutating_actions:
        exercise_recommendation_actions(driver, recorder, section, output_dir, settle_seconds)
    else:
        section.notes.append("Mutating save/skip actions skipped by --no-mutating-actions.")

    classify_canceled(section, recorder.events, "BUG-FE-CANCELED-FETCH-RACE", body_text(driver))
    section.network_event_count = len(recorder.events)
    section.canceled_request_count = sum(1 for event in recorder.events if event.get("canceled"))
    return section


def exercise_recommendation_actions(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    section: AuditSection,
    output_dir: Path,
    settle_seconds: float,
) -> None:
    for label, bug_id in (("Simpan", "BUG-FE-CANCELED-FETCH-RACE"), ("Lewati", "BUG-FE-CANCELED-FETCH-RACE")):
        before = len(recorder.events)
        try:
            buttons = [
                button
                for button in driver.find_elements(By.TAG_NAME, "button")
                if label.lower() in (button.text or "").lower() and button.is_displayed() and button.is_enabled()
            ]
            if not buttons:
                section.notes.append(f"No enabled {label} button found on recommendations page.")
                continue
            buttons[0].click()
            time.sleep(settle_seconds)
            recorder.poll(f"recommendations-{label.lower()}")
            text = body_text(driver)
            timeout_hits = visible_timeout_texts(text)
            add_check(
                section,
                bug_id,
                f"{label} action does not leave visible timeout state",
                not timeout_hits,
                evidence={"timeout_texts": timeout_hits},
            )
            capture_artifacts(driver, output_dir, section, f"recommendations_after_{label.lower()}")
            classify_canceled(section, recorder.events[before:], bug_id, text)
        except WebDriverException as exc:
            section.notes.append(f"{label} interaction failed: {str(exc)[:300]}")
            add_check(
                section,
                bug_id,
                f"{label} action executed",
                False,
                evidence={"error": str(exc)[:300]},
            )


def classify_canceled(section: AuditSection, events: list[dict[str, Any]], bug_id: str, current_text: str) -> None:
    canceled = [event for event in events if event.get("canceled")]
    timeout_visible = bool(visible_timeout_texts(current_text))
    unexpected = timeout_visible and bool(canceled)
    add_check(
        section,
        bug_id,
        "canceled requests do not produce current visible timeout state",
        not unexpected,
        evidence={
            "canceled_count": len(canceled),
            "visible_timeout": timeout_visible,
            "classification": "unexpected" if unexpected else "expected-or-benign",
        },
    )


def audit_theme_toggle(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    base_url: str,
    output_dir: Path,
    routes: list[str],
    settle_seconds: float,
) -> AuditSection:
    section = AuditSection(name="Theme Toggle", route=",".join(routes))
    for route in routes:
        recorder.clear()
        driver.get(f"{base_url.rstrip('/')}{route}")
        time.sleep(settle_seconds)
        recorder.poll(f"theme-{route}-load")
        capture_artifacts(driver, output_dir, section, f"theme_{safe_name(route)}_before")
        before = theme_state(driver)
        transitions: list[dict[str, Any]] = []
        button_found = True
        try:
            for _ in range(5):
                button = find_theme_button(driver)
                if button is None:
                    button_found = False
                    break
                before_click = theme_state(driver)
                activation = activate_theme_button(driver, button, before_click)
                transition = theme_state(driver)
                transition["activation"] = activation
                transitions.append(transition)
        except WebDriverException as exc:
            section.notes.append(f"theme toggle click failed on {route}: {str(exc)[:300]}")
        capture_artifacts(driver, output_dir, section, f"theme_{safe_name(route)}_after_clicks")
        after = theme_state(driver)
        driver.refresh()
        time.sleep(settle_seconds)
        reloaded = theme_state(driver)
        recorder.poll(f"theme-{route}-reload")
        capture_artifacts(driver, output_dir, section, f"theme_{safe_name(route)}_after_reload")

        spinner_stuck = after.get("spinner_count", 0) > 0 or reloaded.get("spinner_count", 0) > 0
        persisted = after.get("local_storage_theme") == reloaded.get("html_theme")
        changed_at_least_once = len({item.get("html_theme") for item in transitions}) > 1
        add_check(
            section,
            "BUG-FE-THEME-TOGGLE-STUCK",
            f"theme button exists on {route}",
            button_found,
            evidence={"before": before},
        )
        add_check(
            section,
            "BUG-FE-THEME-TOGGLE-STUCK",
            f"theme changes after repeated clicks on {route}",
            changed_at_least_once,
            evidence={"transitions": transitions},
        )
        add_check(
            section,
            "BUG-FE-THEME-TOGGLE-STUCK",
            f"theme toggle has no stuck spinner on {route}",
            not spinner_stuck,
            evidence={"after": after, "reloaded": reloaded},
        )
        add_check(
            section,
            "BUG-FE-THEME-TOGGLE-STUCK",
            f"theme persists after reload on {route}",
            persisted,
            evidence={"after": after, "reloaded": reloaded},
        )

    section.network_event_count = len(recorder.events)
    section.canceled_request_count = sum(1 for event in recorder.events if event.get("canceled"))
    return section


def find_theme_button(driver: WebDriver):
    script = """
    return Array.from(document.querySelectorAll('button')).find((button) => {
      const label = String(button.getAttribute('aria-label') || '').toLowerCase();
      return label.includes('theme');
    }) || null;
    """
    try:
        return driver.execute_script(script)
    except WebDriverException:
        return None


def activate_theme_button(driver: WebDriver, button: Any, before_click: dict[str, Any]) -> dict[str, Any]:
    """Activate the theme toggle and record whether ChromeDriver needed a JS fallback.

    On this Windows/ChromeDriver setup, authenticated app pages can report a
    successful WebDriver click without dispatching a trusted click event. The
    fallback keeps the semantic audit rerunnable while preserving that evidence.
    """
    activation: dict[str, Any] = {"method": "webdriver-click", "fallback": False}
    try:
        button.click()
        time.sleep(0.35)
    except WebDriverException as exc:
        activation = {
            "method": "js-click-after-webdriver-error",
            "fallback": True,
            "webdriver_error": str(exc)[:160],
        }
        driver.execute_script("arguments[0].click();", button)
        time.sleep(0.35)
        return activation

    after_click = theme_state(driver)
    unchanged = (
        after_click.get("html_theme") == before_click.get("html_theme")
        and after_click.get("local_storage_theme") == before_click.get("local_storage_theme")
        and after_click.get("button_label") == before_click.get("button_label")
    )
    if unchanged:
        activation = {"method": "js-click-after-webdriver-no-state-change", "fallback": True}
        driver.execute_script("arguments[0].click();", button)
        time.sleep(0.35)
    return activation


def theme_state(driver: WebDriver) -> dict[str, Any]:
    script = """
    const button = Array.from(document.querySelectorAll('button')).find((node) => {
      const label = String(node.getAttribute('aria-label') || '').toLowerCase();
      return label.includes('theme');
    });
    return {
      html_theme: document.documentElement.getAttribute('data-theme'),
      color_scheme: document.documentElement.style.colorScheme,
      local_storage_theme: localStorage.getItem('scpa_theme'),
      button_label: button ? button.getAttribute('aria-label') : null,
      spinner_count: button ? button.querySelectorAll('.animate-spin, [role="status"]').length : 0,
      button_text: button ? String(button.textContent || '').trim() : null,
      svg_count: button ? button.querySelectorAll('svg').length : 0,
      button_rect: button ? (() => { const r = button.getBoundingClientRect(); return {width: r.width, height: r.height}; })() : null,
    };
    """
    try:
        return driver.execute_script(script)
    except WebDriverException as exc:
        return {"error": str(exc)[:200]}


def audit_skill_autocomplete(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    base_url: str,
    api_base: str,
    output_dir: Path,
    settle_seconds: float,
) -> AuditSection:
    section = AuditSection(name="Skills Autocomplete", route="/profile,/onboarding")

    api_results: dict[str, Any] = {}
    for query in SKILL_QUERIES:
        status, payload = http_json(
            f"{api_base.rstrip('/')}/api/skills/search?{urlencode({'q': query, 'limit': 20})}",
            timeout=15,
        )
        skills = payload.get("skills", []) if isinstance(payload, dict) else []
        names = [item.get("name") for item in skills if isinstance(item, dict)]
        api_results[query] = {"status": status, "count": len(names), "names": names[:20]}

    add_check(
        section,
        "BUG-DATA-SKILL-AUTOCOMPLETE-SPARSE",
        "skill search API returns several suggestions for query s",
        api_results.get("s", {}).get("count", 0) >= 5,
        evidence=api_results.get("s", {}),
    )
    for query, expected in {
        "machine": "Machine",
        "data": "Data",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "english": "English",
        "credit": "Credit",
    }.items():
        names = api_results.get(query, {}).get("names", [])
        add_check(
            section,
            "BUG-DATA-SKILL-AUTOCOMPLETE-SPARSE",
            f"skill search API returns relevant suggestions for {query}",
            any(expected.lower() in str(name).lower() for name in names),
            evidence=api_results.get(query, {}),
        )

    recorder.clear()
    driver.get(f"{base_url.rstrip('/')}/profile")
    time.sleep(settle_seconds)
    recorder.poll("skills-profile-load")
    capture_artifacts(driver, output_dir, section, "skills_profile_before")
    try:
        edit_buttons = [
            button
            for button in driver.find_elements(By.TAG_NAME, "button")
            if "edit" in (button.text or "").lower() and button.is_displayed() and button.is_enabled()
        ]
        if edit_buttons:
            click_with_condition_fallback(
                driver,
                edit_buttons[0],
                lambda: bool(driver.find_elements(By.CSS_SELECTOR, "input[aria-controls='skill-suggestions']")),
            )
        ui_results = exercise_skill_input(driver, recorder, section)
        capture_artifacts(driver, output_dir, section, "skills_profile_after_queries")
        add_check(
            section,
            "BUG-DATA-SKILL-AUTOCOMPLETE-SPARSE",
            "profile autocomplete displays suggestions for tested queries",
            all(item.get("count", 0) > 0 for item in ui_results.values()),
            evidence=ui_results,
        )
        duplicate_ok = test_duplicate_skill_not_added(driver, recorder, section)
        add_check(
            section,
            "BUG-DATA-SKILL-AUTOCOMPLETE-SPARSE",
            "duplicate selected skill is not added twice in profile UI",
            duplicate_ok,
            evidence={},
        )
    except WebDriverException as exc:
        section.notes.append(f"profile skill autocomplete interaction failed: {str(exc)[:300]}")
        add_check(
            section,
            "BUG-DATA-SKILL-AUTOCOMPLETE-SPARSE",
            "profile autocomplete interaction executed",
            False,
            evidence={"error": str(exc)[:300]},
        )

    driver.get(f"{base_url.rstrip('/')}/onboarding")
    time.sleep(settle_seconds)
    recorder.poll("skills-onboarding-load")
    capture_artifacts(driver, output_dir, section, "skills_onboarding")
    text = body_text(driver)
    add_check(
        section,
        "BUG-DATA-SKILL-AUTOCOMPLETE-SPARSE",
        "onboarding skill editor is present",
        "Skills" in text or "Keahlian" in text,
        evidence={"body_text_length": len(text)},
    )

    section.network_event_count = len(recorder.events)
    section.canceled_request_count = sum(1 for event in recorder.events if event.get("canceled"))
    return section


def exercise_skill_input(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    section: AuditSection,
) -> dict[str, dict[str, Any]]:
    input_el = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[aria-controls='skill-suggestions']"))
    )
    ui_results: dict[str, dict[str, Any]] = {}
    for query in ["s", "machine", "data", "docker", "english"]:
        set_react_input_value(driver, input_el, query)
        recorder.wait_for_url(r"/api/skills/search", 5, f"skills-query-{query}")
        time.sleep(0.7)
        recorder.poll(f"skills-query-{query}")
        options = driver.find_elements(By.CSS_SELECTOR, "#skill-suggestions [role='option']")
        names = [option.text.strip() for option in options if option.is_displayed()]
        ui_results[query] = {"count": len(names), "options": names[:10]}
    return ui_results


def test_duplicate_skill_not_added(driver: webdriver.Chrome, recorder: NetworkRecorder, section: AuditSection) -> bool:
    try:
        input_el = driver.find_element(By.CSS_SELECTOR, "input[aria-controls='skill-suggestions']")
        set_react_input_value(driver, input_el, "docker")
        recorder.wait_for_url(r"/api/skills/search", 5, "skills-duplicate")
        time.sleep(0.7)
        options = [option for option in driver.find_elements(By.CSS_SELECTOR, "#skill-suggestions [role='option']") if option.is_displayed()]
        if not options:
            return False
        selected = options[0].text.splitlines()[0].strip()
        dispatch_mousedown(driver, options[0])
        time.sleep(0.3)
        before = body_text(driver).lower().count(selected.lower())
        input_el = driver.find_element(By.CSS_SELECTOR, "input[aria-controls='skill-suggestions']")
        set_react_input_value(driver, input_el, selected)
        add_buttons = [
            button
            for button in driver.find_elements(By.TAG_NAME, "button")
            if button.is_displayed() and button.is_enabled() and (button.text or "").strip() == "+"
        ]
        if add_buttons:
            driver.execute_script("arguments[0].click();", add_buttons[0])
        time.sleep(0.3)
        after = body_text(driver).lower().count(selected.lower())
        return after <= before + 1
    except WebDriverException as exc:
        section.notes.append(f"duplicate skill test failed: {str(exc)[:200]}")
        return False


def click_with_condition_fallback(driver: webdriver.Chrome, element: Any, condition: Callable[[], bool]) -> str:
    try:
        element.click()
        time.sleep(0.35)
        if condition():
            return "webdriver-click"
    except WebDriverException:
        pass
    driver.execute_script("arguments[0].click();", element)
    time.sleep(0.35)
    return "js-click-after-webdriver-no-effect"


def set_react_input_value(driver: webdriver.Chrome, element: Any, value: str) -> None:
    driver.execute_script(
        """
        const input = arguments[0];
        const value = arguments[1];
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        input.focus();
        setter.call(input, value);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        """,
        element,
        value,
    )


def dispatch_mousedown(driver: webdriver.Chrome, element: Any) -> None:
    driver.execute_script(
        """
        arguments[0].dispatchEvent(new MouseEvent('mousedown', {
          bubbles: true,
          cancelable: true,
          view: window
        }));
        """,
        element,
    )


def audit_job_detail_quality(
    driver: webdriver.Chrome,
    recorder: NetworkRecorder,
    base_url: str,
    api_base: str,
    output_dir: Path,
    settle_seconds: float,
) -> AuditSection:
    section = AuditSection(name="Job Detail Quality", route="/jobs/{sample_id}")
    api_status, jobs, _payload = first_jobs(api_base, limit=5)
    add_check(
        section,
        "BUG-DATA-JOB-DESCRIPTION-SHALLOW",
        "sample jobs are available for job detail audit",
        bool(jobs),
        evidence={"api_status": api_status, "sample_count": len(jobs)},
    )

    detail_results: list[dict[str, Any]] = []
    for index, job in enumerate(jobs[:5]):
        job_id = str(job.get("id") or job.get("job_id") or "")
        if not job_id:
            continue
        status, detail = http_json(f"{api_base.rstrip('/')}/api/jobs/{quote(job_id)}")
        if not isinstance(detail, dict):
            detail = {}
        description = str(detail.get("description") or "")
        structured_keys = [
            key
            for key in (
                "description_sections",
                "responsibilities",
                "requirements",
                "nice_to_have",
                "seniority_level",
                "employment_type",
                "job_function",
                "industry",
                "required_skills",
                "preferred_skills",
                "extracted_skills",
            )
            if detail.get(key)
        ]
        recorder.clear()
        driver.get(f"{base_url.rstrip('/')}/jobs/{quote(job_id)}")
        recorder.wait_for_url(r"/api/jobs/", 15, f"job-detail-{index}")
        time.sleep(settle_seconds)
        recorder.poll(f"job-detail-{index}")
        capture_artifacts(driver, output_dir, section, f"job_detail_{index}_{job_id}")
        text = body_text(driver)
        section_labels = [
            label
            for label in (
                "Deskripsi Pekerjaan",
                "Job Responsibilities",
                "Job Requirements",
                "Nice to Have",
                "Seniority",
                "Employment",
                "Job Function",
                "Industry",
                "Skill Gap",
            )
            if label.lower() in text.lower()
        ]
        result = {
            "job_id": job_id,
            "status": status,
            "title": detail.get("title") or job.get("title"),
            "description_chars": len(description),
            "description_lines": len([line for line in description.splitlines() if line.strip()]),
            "structured_keys_present": structured_keys,
            "visible_section_labels": section_labels,
            "body_text_length": len(text),
        }
        detail_results.append(result)

    descriptions_rich = [
        item for item in detail_results
        if item["description_chars"] >= 500 or item["description_lines"] >= 4
    ]
    structured_any = any(item["structured_keys_present"] for item in detail_results)
    skill_gap_visible = any("Skill Gap" in item["visible_section_labels"] for item in detail_results)
    add_check(
        section,
        "BUG-DATA-JOB-DESCRIPTION-SHALLOW",
        "sample job descriptions are richer than one-line summaries",
        len(descriptions_rich) == len(detail_results) and bool(detail_results),
        evidence={"details": detail_results},
    )
    add_check(
        section,
        "BUG-DATA-JOB-DESCRIPTION-SHALLOW",
        "job detail API exposes structured job description fields when available",
        structured_any,
        evidence={"details": detail_results},
    )
    add_check(
        section,
        "BUG-DATA-SKILL-GAP-LOW-CONTEXT",
        "job detail pages display skill gap panel for sampled jobs",
        skill_gap_visible,
        evidence={"details": detail_results},
    )
    add_check(
        section,
        "BUG-DATA-SKILL-GAP-LOW-CONTEXT",
        "skill gap can use required or extracted skills from detail payload",
        any(
            {"required_skills", "preferred_skills", "extracted_skills"}.intersection(set(item["structured_keys_present"]))
            for item in detail_results
        ),
        evidence={"details": detail_results},
    )

    section.network_event_count = len(recorder.events)
    section.canceled_request_count = sum(1 for event in recorder.events if event.get("canceled"))
    return section


def summarize_sections(sections: list[AuditSection]) -> dict[str, Any]:
    checks = [check for section in sections for check in section.checks]
    failures = [check for check in checks if not check.passed]
    return {
        "sections": len(sections),
        "checks": len(checks),
        "passed": len(checks) - len(failures),
        "failed": len(failures),
        "failed_by_bug": {
            bug_id: sum(1 for check in failures if check.bug_id == bug_id)
            for bug_id in sorted({check.bug_id for check in failures})
        },
    }


def markdown_report(
    sections: list[AuditSection],
    output_dir: Path,
    base_url: str,
    api_base: str,
    started_at: str,
    auth: dict[str, Any],
) -> str:
    totals = summarize_sections(sections)
    lines = [
        "# Product Quality Selenium Audit",
        "",
        f"- Started: {started_at}",
        f"- Frontend base URL: `{base_url}`",
        f"- Gateway base URL: `{api_base}`",
        f"- Auth attempted: `{auth.get('attempted', False)}`",
        f"- Auth success: `{auth.get('success', False)}`",
        f"- Checks: {totals['checks']}",
        f"- Passed: {totals['passed']}",
        f"- Failed: {totals['failed']}",
        "",
        "## Section Summary",
        "",
        "| Section | Route | Checks | Failed | Canceled requests |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for section in sections:
        failed = sum(1 for check in section.checks if not check.passed)
        lines.append(
            f"| {section.name} | `{section.route}` | {len(section.checks)} | {failed} | {section.canceled_request_count} |"
        )

    lines.extend(["", "## Findings", ""])
    failures = [check for section in sections for check in section.checks if not check.passed]
    if not failures:
        lines.append("- All semantic checks passed.")
    else:
        for check in failures:
            lines.append(f"- `{check.bug_id}` {check.check}: FAILED ({check.severity}).")
            compact = json.dumps(check.evidence, ensure_ascii=False)
            lines.append(f"  Evidence: `{compact[:500]}`")

    lines.extend(["", "## Artifacts", ""])
    lines.append(f"- Summary JSON: `{rel(output_dir / 'summary.json')}`")
    lines.append(f"- Console logs: `{rel(output_dir / 'console.ndjson')}`")
    lines.append(f"- Network events: `{rel(output_dir / 'network.ndjson')}`")
    lines.append(f"- Screenshots: `{rel(output_dir / 'screenshots')}`")
    lines.append(f"- DOM snapshots: `{rel(output_dir / 'dom_snapshots')}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SCPA semantic frontend product-quality audit.")
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--api-base", default="http://localhost:9000")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--settle-seconds", type=float, default=2.0)
    parser.add_argument("--chrome-binary", default=None)
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--mutating-actions", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    output_dir = args.output.resolve()
    ensure_output_dirs(output_dir)

    started_at = now_iso()
    all_console: list[dict[str, Any]] = []
    sections: list[AuditSection] = []

    driver = build_driver(args.headless, args.width, args.height, args.chrome_binary)
    recorder = NetworkRecorder(driver)
    auth_result: dict[str, Any] = {"attempted": False, "success": False, "has_token": False}

    try:
        driver.set_page_load_timeout(45)
        driver.get(args.base_url)
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
        auth_result = perform_login(driver, args.base_url, args.email, args.password)
        all_console.extend(collect_console(driver, "login"))

        jobs_section = audit_jobs_page(driver, recorder, args.base_url, args.api_base, output_dir, args.settle_seconds)
        sections.append(jobs_section)
        all_console.extend(collect_console(driver, "jobs"))

        if assert_authenticated(AuditSection(name="auth-check", route=""), auth_result):
            rec_section = audit_recommendations_page(
                driver,
                recorder,
                args.base_url,
                output_dir,
                args.settle_seconds,
                args.mutating_actions,
            )
            sections.append(rec_section)
            all_console.extend(collect_console(driver, "recommendations"))

            theme_section = audit_theme_toggle(
                driver,
                recorder,
                args.base_url,
                output_dir,
                ["/analytics", "/recommendations", "/profile", "/dashboard"],
                args.settle_seconds,
            )
            sections.append(theme_section)
            all_console.extend(collect_console(driver, "theme"))

            skill_section = audit_skill_autocomplete(
                driver,
                recorder,
                args.base_url,
                args.api_base,
                output_dir,
                args.settle_seconds,
            )
            sections.append(skill_section)
            all_console.extend(collect_console(driver, "skills"))

            detail_section = audit_job_detail_quality(
                driver,
                recorder,
                args.base_url,
                args.api_base,
                output_dir,
                args.settle_seconds,
            )
            sections.append(detail_section)
            all_console.extend(collect_console(driver, "job-detail"))
        else:
            section = AuditSection(name="Authenticated Checks", route="/recommendations,/profile,/jobs/{id}")
            add_check(
                section,
                "BUG-FE-RECOMMENDATIONS-TIMEOUT",
                "authenticated checks require successful login",
                False,
                evidence={"auth": {k: v for k, v in auth_result.items() if k != "error"}},
            )
            sections.append(section)
    finally:
        recorder.poll("final")
        network_events = recorder.all_events
        driver.quit()

    summary = {
        "started_at": started_at,
        "base_url": args.base_url,
        "api_base": args.api_base,
        "auth": auth_result,
        "totals": summarize_sections(sections),
        "sections": [
            {
                **asdict(section),
                "checks": [asdict(check) for check in section.checks],
            }
            for section in sections
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_ndjson(output_dir / "console.ndjson", all_console)
    write_ndjson(output_dir / "network.ndjson", network_events)
    (output_dir / "product_quality_report.md").write_text(
        markdown_report(sections, output_dir, args.base_url, args.api_base, started_at, auth_result),
        encoding="utf-8",
    )

    print(json.dumps(summary["totals"], indent=2))
    return 1 if summary["totals"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
