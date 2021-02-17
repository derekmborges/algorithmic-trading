from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def get_10_best_active_stocks():
    # Load stocks page
    # options = Options()
    # options.add_argument('--headless')
    # options.add_argument('--disable-gpu')
    # driver = webdriver.Chrome(options = options)
    driver = webdriver.Chrome()
    driver.implicitly_wait(10)
    driver.get("https://finance.yahoo.com/most-active/")
    assert "Most Active Stocks" in driver.title

    # Sort by change descending
    e = driver.find_element(By.XPATH, "//*[text()='% Change']");
    e.click()
    e = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, "//*[text()='% Change']"))
    )
    time.sleep(1)
    e.click()
    e = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.XPATH, "//*[text()='% Change']"))
    )
    time.sleep(1)

    # Grab top 10 stocks
    symbol_links = driver.find_elements_by_xpath("//td[@aria-label='Symbol']/a[contains(@href,'/quote/')]");
    symbols = []
    for symbol_link in symbol_links:
        symbols.append(symbol_link.text)

    driver.close()
    return symbols[:10]
