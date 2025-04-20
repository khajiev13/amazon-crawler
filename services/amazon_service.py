from typing import Dict, List, Optional, Union
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains  # Add this import
from utils.driver_utils import human_like_scroll
from utils.timing_utils import print_timing
import csv
import logging

from utils.driver_utils import random_delay
from utils.security_utils import handle_security_challenges
from py_models.amazon_models import Review, Product, ReviewImage

# Configure module logger
logger = logging.getLogger(__name__)

class AmazonService:
    def __init__(self, driver: WebDriver) -> None:
        self.driver = driver
    
    def perform_search(self, search_term: str, max_retries: int = 3) -> bool:
        """Navigate to Amazon homepage and perform a search like a human
        
        Args:
            search_term: The search term to enter in Amazon search
            max_retries: Maximum number of retries on failure
            
        Returns:
            bool: True if search was successful, False otherwise
        """
        retries = 0
        while retries < max_retries:
            try:
                logger.info(f"Searching attempt {retries + 1} for '{search_term}'...")
                self.driver.get("https://www.amazon.com/")
                random_delay(2.0, 4.0)
                
                # Handle any initial security challenges
                if handle_security_challenges(self.driver):
                    logger.info("Initial security challenge handled, continuing...")
                
                # Wait for search box to be present
                search_box = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "twotabsearchtextbox"))
                )
                
                # Clear any existing text
                search_box.clear()
                
                # Type search term with random delays between characters
                for char in search_term:
                    search_box.send_keys(char)
                    random_delay(0.05, 0.2)  # Short delay between keypresses
                
                random_delay(0.5, 1.5)  # Pause before hitting enter
                
                # Submit the search
                search_box.send_keys(Keys.RETURN)
                
                # Wait for search results to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-result-item"))
                )
                
                return True
                
            except Exception as e:
                retries += 1
                logger.warning(f"Search attempt {retries} failed: {e}")
                if retries >= max_retries:
                    logger.error(f"Error performing search after {max_retries} attempts: {e}")
                    return False
                
                # Wait before retrying
                random_delay(1.0, 2.0)
    
    def extract_product_data(self) -> List[Product]:
        """Extract product titles and detail page links from all available search result pages
        
        Returns:
            List[Product]: A list of Product objects from all pages
        """
        all_products = []
        current_page = 1
        
        try:
            while True:
                logger.info(f"Processing search results page {current_page}...")
                
                # Wait for products to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-result-item"))
                )
                
                # Find all product items on current page
                product_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.s-result-item[data-component-type='s-search-result']")
                
                products_on_page = 0
                for product in product_elements:
                    try:
                        # Extract ASIN directly from the data-asin attribute
                        asin = product.get_attribute("data-asin")
                        
                        # Use the exact class combination from the Amazon page structure
                        title_link_element = product.find_element(By.CSS_SELECTOR, 
                            "a.a-link-normal.s-line-clamp-2.s-link-style.a-text-normal")
                        
                        # Extract title from the span inside h2
                        title = title_link_element.find_element(By.CSS_SELECTOR, "span").text.strip()
                        
                        # Extract the full product link including redirect parameters
                        link = title_link_element.get_attribute("href")
                        
                        # Only add products with both title, link and ASIN
                        if title and link and asin:
                            all_products.append(Product(title=title, link=link, asin=asin))
                            products_on_page += 1
                            logger.info(f"Found product: {title[:50]}... (ASIN: {asin})")
                    
                    except NoSuchElementException:
                        # Try alternative selector pattern that sometimes appears
                        try:
                            # Still get the ASIN even with alternative pattern
                            asin = product.get_attribute("data-asin")
                            
                            title_link_element = product.find_element(By.CSS_SELECTOR, 
                                "a.a-link-normal.s-underline-text.s-underline-link-text.s-link-style.a-text-normal")
                            
                            title = title_link_element.find_element(By.CSS_SELECTOR, "span").text.strip()
                            link = title_link_element.get_attribute("href")
                            
                            if title and link and asin:
                                all_products.append(Product(title=title, link=link, asin=asin))
                                products_on_page += 1
                                logger.info(f"Found product (alt pattern): {title[:50]}... (ASIN: {asin})")
                        except Exception as e:
                            logger.warning(f"Could not find product data with alternative pattern: {e}")
                    
                    except Exception as e:
                        logger.error(f"Error extracting product data: {e}")
                        continue
                
                logger.info(f"Extracted {products_on_page} products from page {current_page}")
                
                # Check if there's a next page button
                try:
                    # Look for the next page button using Amazon's pagination selector
                    next_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                        "a.s-pagination-item.s-pagination-next")
                    
                    # Alternative XPath as suggested in the prompt
                    if not next_buttons:
                        next_buttons = self.driver.find_elements(By.XPATH, 
                            "//a[@class='s-pagination-item s-pagination-next s-pagination-button s-pagination-separator']")
                    
                    # If no next button or it has 's-pagination-disabled' class, we've reached the last page
                    if not next_buttons or "s-pagination-disabled" in next_buttons[0].get_attribute("class"):
                        logger.info(f"Reached the last page ({current_page}). No more products to extract.")
                        break
                    
                    next_button = next_buttons[0]
                    
                    # Scroll to the next button
                    logger.info("Found next page button. Scrolling to it...")
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                        next_button
                    )
                    random_delay(0.5, 1.0)
                    
                    # Highlight the button briefly for visual feedback
                    self.driver.execute_script("""
                        var originalStyle = arguments[0].getAttribute('style');
                        arguments[0].setAttribute('style', 'border: 2px solid red; background: yellow;');
                        setTimeout(function() {
                            arguments[0].setAttribute('style', originalStyle);
                        }, 500);
                    """, next_button)
                    random_delay(0.5, 1.0)
                    
                    # Move to the element with a natural motion
                    actions = ActionChains(self.driver)
                    actions.move_to_element(next_button)
                    actions.pause(0.3)
                    actions.perform()
                    
                    # Click the next button
                    logger.info(f"Navigating to page {current_page + 1}...")
                    next_button.click()
                    
                    # Wait for the new page to load
                    random_delay(2.0, 4.0)
                    
                    # Handle any security challenges that might appear
                    if handle_security_challenges(self.driver):
                        logger.info("Security challenge handled after pagination, continuing...")
                        random_delay(1.0, 2.0)
                    
                    current_page += 1
                    
                except (NoSuchElementException, ElementNotInteractableException) as e:
                    logger.warning(f"No more pages available: {e}")
                    break
                except Exception as e:
                    logger.error(f"Error navigating to next page: {e}")
                    break
            
            logger.info(f"Completed extraction of {len(all_products)} products from {current_page} pages")
            return all_products
            
        except Exception as e:
            logger.error(f"Error finding product elements: {e}")
            return all_products
    
    @print_timing
    def visit_product_details(self, product_link: str) -> bool:
        """Navigate to a product detail page
        
        Args:
            product_link: URL of the product detail page
            
        Returns:
            bool: True if successfully navigated to the page
        """
        try:
            logger.info(f"Visiting product page: {product_link[:60]}...")
            self.driver.get(product_link)
            # random_delay(1.0, 3.0)
            
            # Handle any security challenges that might appear
            if handle_security_challenges(self.driver):
                logger.info("Security challenge handled on product page, continuing...")
                random_delay(1.0, 2.0)
            
            # Wait for the page to load completely
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "productTitle"))
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Error visiting product detail page: {e}")
            return False
    
    def navigate_to_reviews(self) -> bool:
        """Scroll down and click on 'See more reviews' to access the reviews section
        
        Returns:
            bool: True if successfully navigated to reviews
        """
        try:
            # First try to find and click the "See all reviews" link
            logger.info("Looking for reviews link...")
            
            # Scroll down to make review elements visible
            human_like_scroll(self.driver)
            
            # Try multiple possible selectors for the reviews link
            review_link_selectors = [
                "a[data-hook='see-all-reviews-link-foot']",
                "a.a-link-emphasis[href*='customerReviews']",
                "a[href*='#customerReviews']",
                "span.cr-widget-Pagination a",
                "a[data-hook='see-all-reviews-link']"
            ]
            
            for selector in review_link_selectors:
                try:
                    review_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if review_links:
                        for link in review_links:
                            if any(keyword in link.text.lower() for keyword in ["review", "see more", "see all"]):
                                logger.info(f"Found reviews link: '{link.text}'. Clicking...")
                                # Scroll to the element first
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                                random_delay(0.5, 1.5)
                                link.click()
                                
                                # Wait for either reviews page or login form
                                try:
                                    WebDriverWait(self.driver, 10).until(
                                        EC.any_of(
                                            EC.presence_of_element_located((By.ID, "cm_cr-review_list")),
                                            EC.presence_of_element_located((By.ID, "ap_email"))
                                        )
                                    )
                                    
                                    # Check if we need to login
                                    if self._is_login_form_present():
                                        return self._handle_login()
                                    
                                    # If we're here, the reviews loaded without login
                                    return True
                                except:
                                    logger.warning("Neither reviews nor login form found after clicking")
                except:
                    continue
            
            logger.info("Couldn't find a reviews link. Trying direct URL approach...")
            
            # If we can't find a link, try modifying the URL directly
            current_url = self.driver.current_url
            if "/dp/" in current_url:
                # Extract the product ID
                product_id = current_url.split("/dp/")[1].split("/")[0]
                reviews_url = f"https://www.amazon.com/product-reviews/{product_id}"
                logger.info(f"Navigating directly to reviews URL: {reviews_url}")
                self.driver.get(reviews_url)
                random_delay(2.0, 3.0)
                
                # Check if we need to login
                try:
                    # Wait for either reviews page or login form
                    WebDriverWait(self.driver, 10).until(
                        EC.any_of(
                            EC.presence_of_element_located((By.ID, "cm_cr-review_list")),
                            EC.presence_of_element_located((By.ID, "ap_email"))
                        )
                    )
                    
                    # Check if we need to login
                    if self._is_login_form_present():
                        return self._handle_login()
                    
                    # If we're here, the reviews loaded without login
                    return True
                except:
                    logger.warning("Failed to load reviews page via direct URL")
            
            logger.warning("Could not navigate to reviews section")
            return False
        
        except Exception as e:
            logger.error(f"Error navigating to reviews: {e}")
            return False
            
    def navigate_to_reviews_by_asin(self, asin: str, page: int = 1) -> bool:
        """Navigate directly to a product's reviews page using its ASIN and page number
    
        Args:
            asin: Amazon Standard Identification Number
            page: Page number of reviews (default: 1)
    
        Returns:
            bool: True if successfully navigated to reviews
        """
        review_url_templates = [
            "https://www.amazon.com/product-reviews/{asin}/ref=cm_cr_arp_d_viewopt_srt?ie=UTF8&reviewerType=all_reviews&sortBy=recent&pageNumber={page}",
            "https://www.amazon.de/-/en/product-reviews/{asin}/ref=cm_cr_arp_d_viewopt_srt?ie=UTF8&reviewerType=all_reviews&sortBy=recent&pageNumber={page}",
            "https://www.amazon.co.uk/product-reviews/{asin}/ref=cm_cr_arp_d_viewopt_srt?ie=UTF8&reviewerType=all_reviews&sortBy=recent&pageNumber={page}",
        ]
        for url_template in review_url_templates:
            reviews_url = url_template.format(asin=asin, page=page)
            logger.info(f"Trying reviews URL: {reviews_url}")
            self.driver.get(reviews_url)
            random_delay(2.0, 4.0)
            if handle_security_challenges(self.driver):
                logger.info("Security challenge handled on reviews page, continuing...")
                random_delay(1.0, 2.0)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.ID, "cm_cr-review_list")),
                        EC.presence_of_element_located((By.ID, "ap_email"))
                    )
                )
                if self._is_login_form_present():
                    return self._handle_login()
                logger.info(f"Successfully loaded reviews from: {reviews_url}")
                return True
            except TimeoutException:
                logger.warning(f"Reviews not found at {reviews_url}")
                continue
        logger.warning("Could not load reviews from any regional URL.")
        return False
            
    def extract_reviews(self, max_reviews: int = None, comments_in_last_n_days:int = None) -> List[Review]:
        """Extract review data from all review pages
        
        Args:
            max_reviews: Maximum number of reviews to collect (None means collect all)
            
        Returns:
            List[Review]: List of Review objects
        """
        all_reviews = []
        current_page = 1
        
        try:
            logger.info("Extracting review data from all pages...")
            while True:
                logger.info(f"Processing review page {current_page}...")
                
                # Try to translate reviews to English if available
                self._translate_reviews_to_english()
                
                # Look for review elements with multiple selector options
                review_selectors = [
                    "li[data-hook='review'][role='listitem']",
                    "div[data-hook='review']",
                    "li[class*='review'][data-hook='review']"
                ]
                review_elements = []
                for selector in review_selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.info(f"Found {len(elements)} reviews with selector: {selector}")
                        review_elements = elements
                        break
                if not review_elements:
                    logger.warning("No review elements found using any selector pattern")
                
                # Process reviews on the current page
                for review in review_elements:
                    try:
                        # Create a dict to collect all the review data
                        review_data = {}
                        
                        # Extract reviewer name
                        try:
                            reviewer_element = review.find_element(By.CSS_SELECTOR, "span.a-profile-name")
                            review_data["customer_name"] = reviewer_element.text.strip()
                        except:
                            review_data["customer_name"] = "N/A"
                        
                        # Extract location and date
                        try:
                            date_element = review.find_element(By.CSS_SELECTOR, "span[data-hook='review-date']")
                            date_text = date_element.text.strip()
                            # Parse "Reviewed in the United States on February 18, 2025"
                            if "Reviewed in" in date_text:
                                parts = date_text.split("Reviewed in ")
                                if len(parts) > 1:
                                    location_date = parts[1].split(" on ")
                                    if len(location_date) > 1:
                                        review_data["country"] = location_date[0].strip()
                                        review_data["date"] = location_date[1].strip()
                                    else:
                                        review_data["country"] = "N/A"
                                        review_data["date"] = date_text
                                else:
                                    review_data["country"] = "N/A"
                                    review_data["date"] = date_text
                            else:
                                review_data["country"] = "N/A"
                                review_data["date"] = date_text
                        except:
                            review_data["country"] = "N/A"
                            review_data["date"] = "N/A"
                        
                        # Extract review title
                        try:
                            title_element = review.find_element(By.CSS_SELECTOR, "a[data-hook='review-title']")
                            review_data["title"] = title_element.text.strip()
                        except:
                            try:
                                title_element = review.find_element(By.CSS_SELECTOR, "span[data-hook='review-title']")
                                review_data["title"] = title_element.text.strip()
                            except:
                                review_data["title"] = "N/A"
                        
                        # Extract star rating
                        try:
                            rating_element = review.find_element(By.CSS_SELECTOR, "i[data-hook='review-star-rating']")
                            # Get the class that contains the star rating (e.g., "a-star-5")
                            classes = rating_element.get_attribute("class")
                            for css_class in classes.split():
                                if css_class.startswith("a-star-"):
                                    review_data["rating"] = css_class.split("-")[-1]
                                    break
                            # Fallback to text extraction if class parsing fails
                            if review_data["rating"] == "N/A":
                                rating_text = rating_element.text.strip()
                                if "out of" in rating_text:
                                    review_data["rating"] = rating_text.split(" out of")[0]
                        except:
                            try:
                                rating_element = review.find_element(By.CSS_SELECTOR, "i[data-hook='cmps-review-star-rating']")
                                # Get the class that contains the star rating
                                classes = rating_element.get_attribute("class")
                                for css_class in classes.split():
                                    if css_class.startswith("a-star-"):
                                        review_data["rating"] = css_class.split("-")[-1]
                                        break
                                # Fallback to text extraction
                                if review_data["rating"] == "N/A":
                                    rating_text = rating_element.text.strip()
                                    if "out of" in rating_text:
                                        review_data["rating"] = rating_text.split(" out of")[0]
                            except:
                                review_data["rating"] = "N/A"
                        
                        # Extract review text
                        try:
                            body_element = review.find_element(By.CSS_SELECTOR, "span[data-hook='review-body']")
                            review_data["text"] = body_element.text.strip()
                        except:
                            review_data["text"] = "N/A"
                        
                        # Extract review images if present
                        try:
                            # Look for review images
                            image_elements = review.find_elements(By.CSS_SELECTOR, ".review-image-tile")
                            if image_elements:
                                images = []
                                for img in image_elements:
                                    # Get thumbnail URL
                                    thumbnail_url = img.get_attribute("src")
                                    # Convert to full-size image URL by replacing size indicator
                                    full_url = thumbnail_url
                                    if thumbnail_url and "_SY88" in thumbnail_url:
                                        full_url = thumbnail_url.replace("._SY88", "._SL1600_")
                                    images.append(ReviewImage(thumbnail_url=thumbnail_url, full_size_url=full_url))
                                review_data["images"] = images
                        except:
                            review_data["images"] = []
                        
                        # Extract if this is a verified purchase
                        try:
                            verified_badge = review.find_elements(By.CSS_SELECTOR, "span[data-hook='avp-badge']")
                            if verified_badge and "verified purchase" in verified_badge[0].text.lower():
                                review_data["verified_purchase"] = True
                            else:
                                review_data["verified_purchase"] = False
                        except:
                            review_data["verified_purchase"] = False
                        
                        # Extract helpful votes count
                        try:
                            # First try to find the helpful vote count element
                            helpful_elements = review.find_elements(By.CSS_SELECTOR, ".cr-vote-text")
                            if helpful_elements:
                                helpful_text = helpful_elements[0].text.strip()
                                # Parse text like "X people found this helpful"
                                if "people found this helpful" in helpful_text.lower():
                                    count = helpful_text.split("people")[0].strip()
                                    review_data["helpful_count"] = int(count)
                                elif "person found this helpful" in helpful_text.lower():
                                    review_data["helpful_count"] = 1
                                else:
                                    review_data["helpful_count"] = 0
                            else:
                                review_data["helpful_count"] = 0
                        except:
                            review_data["helpful_count"] = 0
                        
                        # Create a Review object and append to the list
                        review_obj = Review(**review_data)
                        logger.info(f"Extracted review: '{review_obj.title[:30]}...'")
                        logger.info(f"  Customer: {review_obj.customer_name} | Country: {review_obj.country} | Rating: {review_obj.rating}")
                        if review_obj.images:
                            logger.info(f"  Images: {len(review_obj.images)} found")
                        all_reviews.append(review_obj)
                        
                        # If we reached the maximum number of reviews, stop
                        if max_reviews is not None and len(all_reviews) >= max_reviews:
                            logger.info(f"Reached maximum number of reviews: {max_reviews}")
                            return all_reviews
                    except Exception as e:
                        logger.error(f"Error extracting individual review data: {e}")
                        continue
                
                # Check if there's a next page
                if not self._has_next_page():
                    logger.info(f"No more review pages found after page {current_page}")
                    break
                
                # Go to the next page
                logger.info(f"Navigating to the next page of reviews...")
                if not self._go_to_next_page():
                    logger.warning(f"Failed to navigate to next page after page {current_page}")
                    break
                current_page += 1
                random_delay(2.0, 3.0)  # Delay between pages
            
            logger.info(f"Collected a total of {len(all_reviews)} reviews from {current_page} pages")
        except Exception as e:
            logger.error(f"Error extracting review data: {e}")
        
        return all_reviews
    
    def _has_next_page(self) -> bool:
        """Check if there's a next page of reviews
        
        Returns:
            bool: True if there's a next page, False otherwise
        """
        try:
            # Find the pagination element
            pagination = self.driver.find_elements(By.CSS_SELECTOR, "ul.a-pagination")
            if not pagination:
                return False
            
            # Look for the "Next page" button that's not disabled
            next_buttons = self.driver.find_elements(By.CSS_SELECTOR, "li.a-last")
            if not next_buttons:
                return False
            
            # If the next button has class "a-disabled", there's no next page
            return "a-disabled" not in next_buttons[0].get_attribute("class")
        except Exception as e:
            logger.error(f"Error checking for next page: {e}")
            return False
    
    def _go_to_next_page(self) -> bool:
        """Navigate to the next page of reviews using direct URL
        
        Returns:
            bool: True if successfully navigated to the next page
        """
        try:
            # Get current URL
            current_url = self.driver.current_url
            
            # Extract current page number
            current_page = 1
            if "pageNumber=" in current_url:
                current_page = int(current_url.split("pageNumber=")[1].split("&")[0])
            
            # Construct URL for the next page
            next_page = current_page + 1
            next_url = current_url.replace(f"pageNumber={current_page}", f"pageNumber={next_page}")
            if "pageNumber=" not in next_url:
                # Add page parameter if not present
                if "?" in next_url:
                    next_url += f"&pageNumber={next_page}"
                else:
                    next_url += f"?pageNumber={next_page}"
            
            logger.info(f"Navigating directly to page {next_page} using URL")
            self.driver.get(next_url)
            
            # Wait for the new page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "cm_cr-review_list"))
            )
            return True
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False

    def save_reviews_to_csv(self, product_title: str, reviews: List[Review], 
                            filename: str = "amazon_reviews.csv") -> None:
        """Save the reviews data to a CSV file
        
        Args:
            product_title: Title of the product
            reviews: List of Review objects
            filename: Name of the output CSV file
        """
        # Create a safe filename from the product title
        safe_title = "".join([c if c.isalnum() else "_" for c in product_title[:30]])
        
        # Create unique filename with product title
        filename_parts = filename.split(".")
        product_filename = f"{filename_parts[0]}_{safe_title}.{filename_parts[1]}"
        
        with open(product_filename, 'w', newline='', encoding='utf-8') as csvfile:
            if not reviews:
                logger.warning(f"No reviews to save for {product_title}")
                return
                
            # Convert reviews to dict for CSV writing using model_dump instead of dict
            reviews_dict = [review.model_dump(exclude={'images'}) for review in reviews]
            # Add image URLs as comma-separated string
            for i, review in enumerate(reviews):
                reviews_dict[i]['image_urls'] = ','.join([img.full_size_url for img in review.images]) if review.images else ''
                
            fieldnames = reviews_dict[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for review in reviews_dict:
                writer.writerow(review)
        
        logger.info(f"Reviews saved to {product_filename}")

    def _handle_login(self, email="raxmon1710@gmail.com", password="Forexuzb8080") -> bool:
        """Handle Amazon login process when prompted
    
        Args:
            email: Amazon account email
            password: Amazon account password
    
        Returns:
            bool: True if login successful and reviews loaded
        """
        try:
            logger.info("Login form detected. Attempting to sign in...")
            # Enter email
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "ap_email"))
            )
            email_field.clear()
            for char in email:
                email_field.send_keys(char)
                random_delay(0.05, 0.15)
    
            # Click continue after entering email
            continue_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "continue"))
            )
            random_delay(0.5, 1.0)
            continue_button.click()
    
            # Enter password
            password_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "ap_password"))
            )
            for char in password:
                password_field.send_keys(char)
                random_delay(0.05, 0.15)
    
            # Click sign-in
            signin_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "signInSubmit"))
            )
            random_delay(10, 14.0)
            signin_button.click()
    
            # Wait for one of several possible outcomes
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.ID, "cm_cr-review_list")),  # Success
                        EC.presence_of_element_located((By.ID, "auth-error-message-box")),  # Login error
                        EC.presence_of_element_located((By.ID, "ap_captcha_img")),  # Captcha
                        EC.presence_of_element_located((By.ID, "auth-mfa-otpcode")),  # MFA
                        EC.presence_of_element_located((By.ID, "cvf-page-content"))  # Additional verification
                    )
                )
            except TimeoutException:
                logger.error("Timed out waiting for login result or additional verification.")
                return False
    
            # Check for successful login
            if self.driver.find_elements(By.ID, "cm_cr-review_list"):
                logger.info("Successfully logged in and loaded reviews")
                return True
    
            # Check for login error
            if self.driver.find_elements(By.ID, "auth-error-message-box"):
                logger.error("Login failed: Incorrect credentials or Amazon blocked login.")
                return False
    
            # Check for captcha or additional verification
            if self.driver.find_elements(By.ID, "ap_captcha_img"):
                logger.error("Amazon presented a CAPTCHA. Manual intervention required.")
                return False
            if self.driver.find_elements(By.ID, "auth-mfa-otpcode") or self.driver.find_elements(By.ID, "cvf-page-content"):
                logger.error("Amazon requires additional verification (MFA/OTP). Manual intervention required.")
                return False
    
            logger.error("Unknown login outcome. Could not proceed.")
            return False
    
        except Exception as e:
            logger.error(f"Error during login process: {e}")
            return False

    @staticmethod
    def save_to_csv(products: List[Union[Product, Dict[str, str]]], filename: str = "amazon_smarttvs.csv") -> None:
        """Save the extracted data to a CSV file
        
        Args:
            products: List of Product objects or product dictionaries
            filename: Name of the output CSV file
        """
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            # If products list is empty, create empty file with headers
            if not products:
                writer = csv.DictWriter(csvfile, fieldnames=['title', 'link', 'asin'])
                writer.writeheader()
                logger.warning(f"Empty product list. Created {filename} with headers only.")
                return
            
            # Handle first product to determine field names
            first_product = products[0]
            # Convert first product to dict if it's a Pydantic model
            first_dict = first_product.model_dump()
            fieldnames = first_dict.keys()
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Process all products
            for product in products:
                # Convert to dict if it's a Pydantic model
                writer.writerow(product.model_dump())
        
        logger.info(f"Data saved to {filename}")
    @print_timing
    def filter_products_by_os(self, products: List[Product], os_keyword: str = "roku") -> List[Product]:
        """Filter products based on their operating system information
        
        Args:
            products: List of Product objects to filter
            os_keyword: Keyword to filter operating systems (default: "roku")
            
        Returns:
            List[Product]: Filtered list of products with matching operating system
        """
        logger.info(f"Filtering products by operating system keyword: '{os_keyword}'")
        validated_products: List[Product] = []
        total_products: int = len(products)
        
        # Process each product
        for i, product in enumerate(products):
            logger.info(f"Checking product {i+1}/{total_products}: {product.title[:50]}...")
            
            if not self.visit_product_details(product.link):
                logger.warning(f"Could not visit product page for: {product.title[:30]}... Skipping.")
                continue
            
            try:
                
                is_matching_os: bool = False
                
                # First attempt: Check for system section in the expandable sections
                is_matching_os = self._check_system_expandable_section(product, os_keyword)
                
                # Second attempt: Look for operating system in product comparison tables
                if not is_matching_os:
                    is_matching_os = self._check_comparison_tables(product, os_keyword)
                
                # Third attempt: Look for operating system in specification tables
                if not is_matching_os:
                    is_matching_os = self._check_specification_tables(product, os_keyword)
                
                # Add product to validated list if OS matches
                if is_matching_os:
                    validated_products.append(product)
                else:
                    logger.info(f"Product is NOT a {os_keyword.capitalize()} TV, skipping: {product.title[:30]}...")
                
            except Exception as e:
                logger.warning(f"Error checking if product matches OS criteria: {e}")
        
        logger.info(f"Filtering complete: {len(validated_products)}/{total_products} products have {os_keyword.capitalize()} OS")
        return validated_products
    
    @print_timing
    def _check_system_expandable_section(self, product: Product, os_keyword: str) -> bool:
        """Check for operating system in expandable system sections
        
        Args:
            product: Product object to check
            os_keyword: Keyword to match in operating system
            
        Returns:
            bool: True if operating system matches keyword
        """
        try:
            # Find system section by looking for the heading
            system_headings = self.driver.find_elements(
                By.XPATH, 
                "//span[contains(@class, 'a-expander-prompt') and contains(text(), 'System')]"
            )
            
            if system_headings:
                # Find the parent container that holds the system information
                for heading in system_headings:
                    try:
                        # Navigate to the expanded content section
                        section = heading.find_element(By.XPATH, "./ancestor::div[contains(@class, 'a-expander-container')]")
                        
                        # Look for operating system row
                        os_rows = section.find_elements(
                            By.XPATH,
                            ".//tr[.//th[contains(text(), 'Operating System')]]"
                        )
                        
                        if os_rows:
                            # Get the OS value (in the td element)
                            os_value = os_rows[0].find_element(By.TAG_NAME, "td").text.strip()
                            logger.info(f"Found Operating System: {os_value} for product: {product.title[:30]}...")
                            
                            # Check if OS contains the keyword
                            if os_keyword.lower() in os_value.lower():
                                logger.info(f"Product is a {os_keyword.capitalize()} TV: {product.title[:30]}...")
                                return True
                            else:
                                logger.info(f"Product is NOT a {os_keyword.capitalize()}: {product.title[:30]}...")
                    except Exception as e:
                        logger.warning(f"Error checking system details in section: {e}")
        except Exception as e:
            logger.warning(f"Error finding system expandable sections: {e}")
        
        return False
    
    @print_timing
    def _check_comparison_tables(self, product: Product, os_keyword: str) -> bool:
        """Check for operating system in product comparison tables
        
        Args:
            product: Product object to check
            os_keyword: Keyword to match in operating system
            
        Returns:
            bool: True if operating system matches keyword
        """
        try:
            # Look for rows with "operating system" in product comparison tables
            os_rows = self.driver.find_elements(
                By.XPATH,
                "//tr[.//span[contains(text(), 'operating system')]]"
            )
            
            if os_rows:
                for row in os_rows:
                    try:
                        # Find all td elements in the row
                        cells = row.find_elements(By.TAG_NAME, "td")
                        
                        for cell in cells:
                            try:
                                # Look for spans that contain text within the cell
                                value_spans = cell.find_elements(
                                    By.XPATH, 
                                    ".//span[contains(@class, 'a-color-base')]"
                                )
                                
                                for span in value_spans:
                                    os_value = span.text.strip()
                                    if os_value and os_value != "—":  # Skip empty or dash values
                                        logger.info(f"Found Operating System in comparison table: {os_value} for product: {product.title[:30]}...")
                                        
                                        # Check if OS contains the keyword
                                        if os_keyword.lower() in os_value.lower():
                                            logger.info(f"Product is a {os_keyword.capitalize()}  (from comparison table): {product.title[:30]}...")
                                            return True
                                        else:
                                            logger.info(f"Product is NOT a {os_keyword.capitalize()} (from comparison table): {product.title[:30]}...")
                                    else:
                                        logger.info(f"Empty or dash value found in comparison table for product: {product.title[:30]}...")
                            except Exception as e:
                                logger.warning(f"Error reading OS value from span: {e}")
                    except Exception as e:
                        logger.warning(f"Error processing cells in OS row: {e}")
            else:
                logger.info(f"No operating system found in comparison tables for: {product.title[:30]}...")
        except Exception as e:
            logger.warning(f"Error checking comparison tables for OS: {e}")
        
        return False
    
    @print_timing
    def _check_specification_tables(self, product: Product, os_keyword: str) -> bool:
        """Check for operating system in specification tables
        
        Args:
            product: Product object to check
            os_keyword: Keyword to match in operating system
            
        Returns:
            bool: True if operating system matches keyword
        """
        try:
            # Look for tables with specification details
            spec_tables = self.driver.find_elements(
                By.XPATH,
                "//table[contains(@class, 'prodDetTable')]"
            )
            
            for table in spec_tables:
                try:
                    # Find rows that mention "operating system"
                    os_rows = table.find_elements(
                        By.XPATH,
                        ".//tr[.//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'operating system')]]"
                    )
                    
                    if os_rows:
                        for row in os_rows:
                            try:
                                # Get the value cell
                                value_cell = row.find_element(By.XPATH, ".//td")
                                os_value = value_cell.text.strip()
                                
                                logger.info(f"Found Operating System in spec table: {os_value} for product: {product.title[:30]}...")
                                
                                # Check if OS contains the keyword
                                if os_keyword.lower() in os_value.lower():
                                    logger.info(f"Product is a {os_keyword.capitalize()}  (from spec table): {product.title[:30]}...")
                                    return True
                                else:
                                    logger.info(f"Product is NOT a {os_keyword.capitalize()}  (from spec table): {product.title[:30]}...")
                            except Exception as e:
                                logger.warning(f"Error reading OS value from spec row: {e}")
                except Exception as e:
                    logger.warning(f"Error processing rows in spec table: {e}")
        except Exception as e:
            logger.warning(f"Error checking spec tables for OS: {e}")
        
        return False

    def _translate_reviews_to_english(self) -> bool:
        """Find and click the translate button to translate reviews to English
        
        Returns:
            bool: True if translate button was found and clicked, False otherwise
        """
        logger.info("Checking for 'Translate all reviews to English' button...")
        try:
            # First try by ID which is faster
            translate_buttons = self.driver.find_elements(By.ID, "a-autoid-21-announce")
            
            # Fallback to data-hook if ID doesn't work or isn't found
            if not translate_buttons:
                translate_buttons = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    "a[data-hook='cr-translate-these-reviews-link']"
                )
            
            if not translate_buttons:
                logger.info("No translate button found on this page.")
                return False
                
            translate_button = translate_buttons[0]
            logger.info("Found 'Translate all reviews to English' button. Preparing to click...")
            
            # Scroll to the button
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                translate_button
            )
            random_delay(0.5, 1.0)
            
            # Hover before clicking
            actions = ActionChains(self.driver)
            actions.move_to_element(translate_button).pause(0.3).perform()
            
            # Click the translate button
            translate_button.click()
            logger.info("Clicked the translate button.")
            
            # Wait for translation to complete
            random_delay(2.0, 4.0)
            
            # Wait for review list to be present again after potential reload
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "cm_cr-review_list"))
            )
            logger.info("Review list confirmed present after translation attempt.")
            return True
            
        except ElementNotInteractableException:
            logger.warning("Translate button found but was not interactable.")
            return False
        except Exception as e:
            logger.warning(f"Error checking for or clicking translate button: {e}")
            return False
        
    def _is_login_form_present(self, timeout=5) -> bool:
        """Check if the Amazon login form is visible."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((By.ID, "ap_email"))
            )
            return True
        except TimeoutException:
            return False