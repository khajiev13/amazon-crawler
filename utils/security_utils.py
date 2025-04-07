#!/usr/bin/env python3
"""
Security utilities for handling website security challenges
Provides functions to detect and handle CAPTCHAs and other security challenges.
"""
from typing import List, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

def handle_security_challenges(driver: WebDriver) -> bool:
    """Handle various Amazon security challenges including CAPTCHAs
    
    Args:
        driver: Selenium WebDriver instance
    
    Returns:
        bool: True if a security challenge was detected and handled, False otherwise
    """
    try:
        # Check for CAPTCHA or security verification
        security_elements = driver.find_elements(By.XPATH, 
            "//*[contains(text(), 'CAPTCHA') or contains(text(), 'robot') or contains(text(), 'verification') or contains(text(), 'unusual activity')]")
        
        if security_elements:
            print("Security challenge detected! Please solve it manually.")
            input("Press Enter once you've solved the challenge...")
            return True
        
        # Check for the image CAPTCHA that Amazon often uses
        captcha_input = driver.find_elements(By.ID, "captchacharacters")
        if captcha_input:
            print("CAPTCHA image detected! Please solve it manually.")
            input("Press Enter once you've solved the CAPTCHA...")
            return True
            
    except Exception as e:
        print(f"Error checking for security challenges: {e}")
    
    return False