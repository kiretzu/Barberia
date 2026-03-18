from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time

def main():
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(service=service, options=options)
    driver.get("http://127.0.0.1:5000/login")
    time.sleep(2)

    driver.find_element(By.NAME, "username").send_keys("admin")
    driver.find_element(By.NAME, "password").send_keys("Admin#2026")
    driver.find_element(By.TAG_NAME, "button").click()

    time.sleep(3)

    driver.find_element(By.NAME, "nombre").send_keys("Carlos")
    driver.find_element(By.NAME, "edad").send_keys("30")
    driver.find_element(By.XPATH, "//button[contains(text(),'Agregar')]").click()

    time.sleep(5)

    driver.quit()

if __name__ == "__main__":
    main()