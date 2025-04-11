from typing import Dict, List, Optional, Union
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains  # Add this import
from utils.driver_utils import human_like_scroll
import csv
import time  # Add this import

from utils.driver_utils import random_delay
from utils.security_utils import handle_security_challenges
from py_models.amazon_models import Review, Product, ReviewImage

class AmazonService:
    def __init__(self, driver: WebDriver) -> None:
        self.driver = driver
    
    def perform_search(self, search_term: str) -> bool:
        """Navigate to Amazon homepage and perform a search like a human
        
        Args:
            search_term: The search term to enter in Amazon search
            
        Returns:
            bool: True if search was successful, False otherwise
        """
        try:
            print("Navigating to Amazon homepage...")
            self.driver.get("https://www.amazon.com/")
            random_delay(2.0, 4.0)
            
            # Handle any initial security challenges
            if handle_security_challenges(self.driver):
                print("Initial security challenge handled, continuing...")
            
            print(f"Searching for '{search_term}'...")
            
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
            print(f"Error performing search: {e}")
            return False
    
    def extract_product_data(self) -> List[Product]:
        """Extract product titles and detail page links from all available search result pages
        
        Returns:
            List[Product]: A list of Product objects from all pages
        """
        all_products = []
        current_page = 1
        
        try:
            while True:
                print(f"Processing search results page {current_page}...")
                
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
                            print(f"Found product: {title[:50]}... (ASIN: {asin})")
                    
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
                                print(f"Found product (alt pattern): {title[:50]}... (ASIN: {asin})")
                        except Exception as e:
                            print(f"Could not find product data with alternative pattern: {e}")
                    
                    except Exception as e:
                        print(f"Error extracting product data: {e}")
                        continue
                
                print(f"Extracted {products_on_page} products from page {current_page}")
                
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
                        print(f"Reached the last page ({current_page}). No more products to extract.")
                        break
                    
                    next_button = next_buttons[0]
                    
                    # Scroll to the next button
                    print(f"Found next page button. Scrolling to it...")
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
                    print(f"Navigating to page {current_page + 1}...")
                    next_button.click()
                    
                    # Wait for the new page to load
                    random_delay(2.0, 4.0)
                    
                    # Handle any security challenges that might appear
                    if handle_security_challenges(self.driver):
                        print("Security challenge handled after pagination, continuing...")
                        random_delay(1.0, 2.0)
                    
                    current_page += 1
                    
                except (NoSuchElementException, ElementNotInteractableException) as e:
                    print(f"No more pages available: {e}")
                    break
                except Exception as e:
                    print(f"Error navigating to next page: {e}")
                    break
            
            print(f"Completed extraction of {len(all_products)} products from {current_page} pages")
            return all_products
            
        except Exception as e:
            print(f"Error finding product elements: {e}")
            return all_products
    
    
    def visit_product_details(self, product_link: str) -> bool:
        """Navigate to a product detail page
        
        Args:
            product_link: URL of the product detail page
            
        Returns:
            bool: True if successfully navigated to the page
        """
        try:
            print(f"Visiting product page: {product_link[:60]}...")
            self.driver.get(product_link)
            random_delay(2.0, 4.0)
            
            # Handle any security challenges that might appear
            if handle_security_challenges(self.driver):
                print("Security challenge handled on product page, continuing...")
                random_delay(1.0, 2.0)
            
            # Wait for the page to load completely
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "productTitle"))
            )
            
            return True
        
        except Exception as e:
            print(f"Error visiting product detail page: {e}")
            return False
    
    def navigate_to_reviews(self) -> bool:
        """Scroll down and click on 'See more reviews' to access the reviews section
        
        Returns:
            bool: True if successfully navigated to reviews
        """
        try:
            # First try to find and click the "See all reviews" link
            print("Looking for reviews link...")
            
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
                                print(f"Found reviews link: '{link.text}'. Clicking...")
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
                                    if self.driver.find_elements(By.ID, "ap_email"):
                                        return self._handle_login()
                                    
                                    # If we're here, the reviews loaded without login
                                    return True
                                except:
                                    print("Neither reviews nor login form found after clicking")
                except:
                    continue
            
            print("Couldn't find a reviews link. Trying direct URL approach...")
            
            # If we can't find a link, try modifying the URL directly
            current_url = self.driver.current_url
            if "/dp/" in current_url:
                # Extract the product ID
                product_id = current_url.split("/dp/")[1].split("/")[0]
                reviews_url = f"https://www.amazon.com/product-reviews/{product_id}"
                print(f"Navigating directly to reviews URL: {reviews_url}")
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
                    if self.driver.find_elements(By.ID, "ap_email"):
                        return self._handle_login()
                    
                    # If we're here, the reviews loaded without login
                    return True
                except:
                    print("Failed to load reviews page via direct URL")
            
            print("Could not navigate to reviews section")
            return False
        
        except Exception as e:
            print(f"Error navigating to reviews: {e}")
            return False
            
    def navigate_to_reviews_by_asin(self, asin: str, page: int = 1) -> bool:
        """Navigate directly to a product's reviews page using its ASIN and page number
        
        Args:
            asin: Amazon Standard Identification Number
            page: Page number of reviews (default: 1)
            
        Returns:
            bool: True if successfully navigated to reviews
        """
        try:
            # Construct direct URL to reviews page with sorting and pagination
            reviews_url = f"https://www.amazon.com/product-reviews/{asin}/ref=cm_cr_arp_d_viewopt_srt?ie=UTF8&reviewerType=all_reviews&sortBy=recent&pageNumber={page}"
            print(f"Navigating directly to reviews page {page} using ASIN: {asin}")
            self.driver.get(reviews_url)
            random_delay(2.0, 4.0)
            
            # Handle any security challenges that might appear
            if handle_security_challenges(self.driver):
                print("Security challenge handled on reviews page, continuing...")
                random_delay(1.0, 2.0)
                
            # Wait for either reviews page or login form
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.ID, "cm_cr-review_list")),
                        EC.presence_of_element_located((By.ID, "ap_email"))
                    )
                )
                
                # Check if we need to login
                if self.driver.find_elements(By.ID, "ap_email"):
                    return self._handle_login()
                
                # If we're here, the reviews loaded without login
                return True
                
            except TimeoutException:
                print("Neither reviews nor login form found after navigation")
                return False
                
        except Exception as e:
            print(f"Error navigating to reviews by ASIN: {e}")
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
            print("Extracting review data from all pages...")
            while True:
                print(f"Processing review page {current_page}...")
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
                        print(f"Found {len(elements)} reviews with selector: {selector}")
                        review_elements = elements
                        break
                if not review_elements:
                    print("No review elements found using any selector pattern")
                
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
                        print(f"Extracted review: '{review_obj.title[:30]}...'")
                        print(f"  Customer: {review_obj.customer_name} | Country: {review_obj.country} | Rating: {review_obj.rating}")
                        if review_obj.images:
                            print(f"  Images: {len(review_obj.images)} found")
                        all_reviews.append(review_obj)
                        
                        # If we reached the maximum number of reviews, stop
                        if max_reviews is not None and len(all_reviews) >= max_reviews:
                            print(f"Reached maximum number of reviews: {max_reviews}")
                            return all_reviews
                    except Exception as e:
                        print(f"Error extracting individual review data: {e}")
                        continue
                
                # Check if there's a next page
                if not self._has_next_page():
                    print(f"No more review pages found after page {current_page}")
                    break
                
                # Go to the next page
                print(f"Navigating to the next page of reviews...")
                if not self._go_to_next_page():
                    print(f"Failed to navigate to next page after page {current_page}")
                    break
                current_page += 1
                random_delay(2.0, 3.0)  # Delay between pages
            
            print(f"Collected a total of {len(all_reviews)} reviews from {current_page} pages")
        except Exception as e:
            print(f"Error extracting review data: {e}")
        
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
            print(f"Error checking for next page: {e}")
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
            
            print(f"Navigating directly to page {next_page} using URL")
            self.driver.get(next_url)
            
            # Wait for the new page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "cm_cr-review_list"))
            )
            return True
        except Exception as e:
            print(f"Error navigating to next page: {e}")
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
                print(f"No reviews to save for {product_title}")
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
        
        print(f"Reviews saved to {product_filename}")

    def _handle_login(self, email="raxmon1710@gmail.com", password="7191710r") -> bool:
        """Handle Amazon login process when prompted
        
        Args:
            email: Amazon account email
            password: Amazon account password
            
        Returns:
            bool: True if login successful and reviews loaded
        """
        try:
            print("Login form detected. Attempting to sign in...")
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
            random_delay(0.5, 1.0)
            signin_button.click()
            
            # Wait for reviews to load after login
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "cm_cr-review_list"))
            )
            print("Successfully logged in and loaded reviews")
            return True
        except Exception as e:
            print(f"Error during login process: {e}")
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
                print(f"Empty product list. Created {filename} with headers only.")
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
        
        print(f"Data saved to {filename}")