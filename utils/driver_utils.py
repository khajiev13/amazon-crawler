#!/usr/bin/env python3
"""
Driver utilities for Selenium WebDriver
Contains functions for setting up and controlling the web driver in a human-like manner.
"""
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver
import time
import random

def setup_driver() -> WebDriver:
    """Configure and return a Selenium WebDriver with anti-detection measures
    
    Returns:
        WebDriver: Configured Chrome WebDriver instance
    """
    options = Options()
    
    # Add realistic Mac user agent
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
    
    # Additional options to avoid detection
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Initialize Chrome driver
    driver = webdriver.Chrome(options=options)
    
    # Set window size to a common resolution
    driver.set_window_size(1366, 768)
    
    # Execute CDP commands to prevent detection
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """
    })
    
    return driver

def random_delay(min_sec: float = 1.0, max_sec: float = 3.0) -> None:
    """Add random delay between actions to appear more human-like
    
    Args:
        min_sec: Minimum seconds to delay
        max_sec: Maximum seconds to delay
    """
    time.sleep(random.uniform(min_sec, max_sec))

def human_like_scroll(driver: WebDriver) -> None:
    """Scroll down the page in a human-like manner
    
    Args:
        driver: Selenium WebDriver instance
    """
    total_height = driver.execute_script("return document.body.scrollHeight")
    viewport_height = driver.execute_script("return window.innerHeight")
    
    scroll_positions = list(range(0, total_height, viewport_height // 2))
    
    for position in scroll_positions:
        # Calculate a random scroll amount
        scroll_amount = position + random.randint(-50, 50)
        scroll_amount = max(0, min(scroll_amount, total_height))
        
        # Scroll to the position
        driver.execute_script(f"window.scrollTo(0, {scroll_amount});")
        
        # Random delay between scrolls
        random_delay(0.1, 0.5)