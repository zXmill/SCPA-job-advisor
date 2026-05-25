import sys
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.keys import Keys

SCRATCH_DIR = Path(r"e:/TUGAS AKHIR/SCPA/browser_screenshots")
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = SCRATCH_DIR / "browser_e2e_results.log"
BASE_URL = "http://localhost:3000"
API_URL = "http://localhost:8000"


def log(msg: str) -> None:
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def get_driver():
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,800")
    driver = webdriver.Chrome(options=options)
    log("Chrome driver started")
    return driver


def shot(driver, name: str) -> None:
    path = SCRATCH_DIR / f"{name}.png"
    driver.save_screenshot(str(path))
    log(f"Screenshot: {path}")


def login(driver):
    log("Navigating to login page...")
    driver.get(f"{BASE_URL}/auth")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
    time.sleep(1)

    # Try to find login form (second tab usually)
    tabs = driver.find_elements(By.CSS_SELECTOR, "button, [role='tab']")
    for tab in tabs:
        if "Masuk" in tab.text or "Login" in tab.text:
            tab.click()
            time.sleep(0.5)
            break

    inputs = driver.find_elements(By.TAG_NAME, "input")
    email_input = None
    password_input = None
    for inp in inputs:
        placeholder = inp.get_attribute("placeholder") or ""
        type_attr = inp.get_attribute("type") or ""
        if "email" in placeholder.lower() or "email" in type_attr:
            email_input = inp
        elif "password" in placeholder.lower() or type_attr == "password":
            password_input = inp

    if not email_input or not password_input:
        log("Could not find email/password inputs")
        shot(driver, "login_form")
        return False

    # Use existing test account or create one
    email_input.clear()
    email_input.send_keys("test@scpa.local")
    password_input.clear()
    password_input.send_keys("TestPass123")

    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        if "Masuk" in btn.text or "Login" in btn.text:
            btn.click()
            break

    time.sleep(2)
    shot(driver, "after_login")
    return True


def check_analytics(driver):
    log("Navigating to Temukan Kerja (analytics)...")
    driver.get(f"{BASE_URL}/analytics")
    wait = WebDriverWait(driver, 20)

    # Wait for either job cards or error/empty state
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='GlassCard'], [role='status'], [role='alert']")))
        time.sleep(3)
        shot(driver, "analytics_page")
        body = driver.find_element(By.TAG_NAME, "body").text
        if "Permintaan kehabisan waktu" in body:
            log("FAIL: Temukan Kerja still shows timeout error")
            return False
        if "Memuat" in body and "lowongan" not in body.lower():
            log("WARN: Page still loading")
            return False
        if "posisi tersedia" in body:
            log("PASS: Temukan Kerja loaded successfully")
            return True
        log(f"Temukan Kerja body text: {body[:500]}")
        return True
    except Exception as exc:
        log(f"ERROR waiting for analytics: {exc}")
        shot(driver, "analytics_error")
        return False


def change_skills(driver):
    log("Navigating to profile...")
    driver.get(f"{BASE_URL}/profile")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "button")))
    time.sleep(1)

    # Click Edit
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        if "Edit" in btn.text:
            btn.click()
            time.sleep(1)
            break

    # Add non-tech skill
    skill_input = None
    inputs = driver.find_elements(By.TAG_NAME, "input")
    for inp in inputs:
        placeholder = inp.get_attribute("placeholder") or ""
        if "keahlian" in placeholder.lower() or "skill" in placeholder.lower():
            skill_input = inp
            break

    if skill_input:
        skill_input.clear()
        skill_input.send_keys("Marketing")
        skill_input.send_keys(Keys.RETURN)
        time.sleep(0.5)
        skill_input.clear()
        skill_input.send_keys("Canva")
        skill_input.send_keys(Keys.RETURN)
        time.sleep(0.5)
        log("Added non-tech skills: Marketing, Canva")
    else:
        log("Could not find skill input")

    # Save
    for btn in buttons:
        if "Simpan" in btn.text:
            btn.click()
            time.sleep(2)
            break

    shot(driver, "profile_after_save")
    return True


def check_recommendations(driver):
    log("Navigating to recommendations...")
    driver.get(f"{BASE_URL}/recommendations?refresh={int(time.time()*1000)}")
    wait = WebDriverWait(driver, 20)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='GlassCard'], [role='alert']")))
        time.sleep(5)
        shot(driver, "recommendations_page")
        body = driver.find_element(By.TAG_NAME, "body").text
        if "Permintaan kehabisan waktu" in body:
            log("FAIL: Recommendations timeout")
            return False
        if "Belum ada rekomendasi" in body:
            log("INFO: No recommendations yet")
            return True
        log("PASS: Recommendations loaded")
        # Check for non-tech job titles
        non_tech_found = any(k in body.lower() for k in ["marketing", "designer", "sales", "hr ", "finance", "teacher", "accountant"])
        if non_tech_found:
            log("PASS: Non-tech recommendations found")
        else:
            log("INFO: No obvious non-tech titles in recommendations, but page loaded")
        return True
    except Exception as exc:
        log(f"ERROR waiting for recommendations: {exc}")
        shot(driver, "recommendations_error")
        return False


def main():
    log("\n=== Browser E2E Test Start ===")
    driver = get_driver()
    try:
        # Check if already logged in
        driver.get(f"{BASE_URL}/dashboard")
        time.sleep(2)
        if "/auth" in driver.current_url:
            log("Not logged in, attempting login...")
            if not login(driver):
                log("Login failed, aborting")
                return
        else:
            log("Already logged in")

        # Test Temukan Kerja
        ok1 = check_analytics(driver)

        # Change skills to non-tech
        change_skills(driver)

        # Check recommendations
        ok2 = check_recommendations(driver)

        log(f"\n=== Results: analytics={ok1}, recommendations={ok2} ===")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
