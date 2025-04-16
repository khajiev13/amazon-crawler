import argparse
import csv
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from utils.driver_utils import setup_driver, random_delay
from services.amazon_service import AmazonService
from selenium import webdriver

from utils.timing_utils import print_timing

# Constants
DEFAULT_SEARCH_TERM = "smart tvs"
DEFAULT_OUTPUT_FILE = "amazon_smarttvs.csv"
DEFAULT_MAX_PRODUCTS = 5
REVIEWS_DIR = "reviews"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Amazon Smart TV Crawler")
    parser.add_argument("--search", type=str, default=DEFAULT_SEARCH_TERM, 
                      help=f"Search term to use (default: '{DEFAULT_SEARCH_TERM}')")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT_FILE,
                      help=f"Output CSV filename (default: {DEFAULT_OUTPUT_FILE})")
    parser.add_argument("--reviews", action="store_true",
                      help="Scrape product reviews (default: False)")
    parser.add_argument("--max-products", type=int, default=DEFAULT_MAX_PRODUCTS,
                      help=f"Maximum number of products to process for reviews (default: {DEFAULT_MAX_PRODUCTS})")
    parser.add_argument("--max-reviews", type=int,
                      help="Maximum number of reviews per product to collect (default: 10)")
    parser.add_argument("--input-file", type=str,
                      help="Input CSV file with product links (if already scraped)")
    parser.add_argument("--use-profile", action="store_true", 
                      help="Use your existing Chrome profile with saved logins (default: False)")
    parser.add_argument("--comments-in-last-n-days", type=int,
                      help="Number of days to consider for comments")
    return parser.parse_args()
@print_timing
def setup_environment(use_profile: bool) -> webdriver.Chrome:
    """Set up the WebDriver and environment"""
    if use_profile:
        logger.info("Using your existing Chrome profile with saved logins")
        return setup_driver(use_profile=True)
    return setup_driver()

def load_products_from_csv(input_file: str) -> List[Dict[str, Any]]:
    """Load product data from a CSV file"""
    if not os.path.exists(input_file):
        logger.error(f"Input file not found: {input_file}")
        return []
    
    logger.info(f"Loading products from {input_file}")
    with open(input_file, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        products = list(reader)
    
    logger.info(f"Loaded {len(products)} products from CSV")
    return products
@print_timing
def scrape_products(amazon_service: AmazonService, search_term: str, output_file: str) -> List[Dict[str, Any]]:
    """Scrape products from Amazon based on search term"""
    logger.info(f"Starting Amazon crawler with search term: '{search_term}'")
    logger.info(f"Results will be saved to: {output_file}")
    
    if not amazon_service.perform_search(search_term):
        logger.error("Failed to perform search. Exiting.")
        return []
    
    random_delay()
    
    logger.info("Extracting product data...")
    products = amazon_service.extract_product_data()

    #Filter out products based on operating system info
    filtered_products = amazon_service.filter_products_by_os(products, "Roku")
    
    logger.info(f"Found {len(products)} products.")
    
    # Save data to CSV
    amazon_service.save_to_csv(filtered_products, output_file)
    return products
@print_timing
def process_product_reviews(
    amazon_service: AmazonService, 
    products: List[Dict[str, Any]], 
    max_products: int, 
    max_reviews: Optional[int],
    comments_in_last_n_days: Optional[int]
) -> None:
    """Process reviews for the given products"""
    if not products:
        logger.warning("No products to process for reviews")
        return
    
    logger.info(f"Starting to collect reviews for up to {max_products} products...")
    
    # Create reviews directory if it doesn't exist
    reviews_dir = Path(REVIEWS_DIR)
    reviews_dir.mkdir(exist_ok=True)
    
    # Process each product (limiting to max_products)
    for i, product in enumerate(products[:max_products]):
        logger.info(f"\nProcessing product {i+1}/{min(max_products, len(products))}")
        logger.info(f"Title: {product['title'][:50]}...")
        
        # Navigate to comments using asin
        if not amazon_service.navigate_to_reviews_by_asin(product['asin']):
            logger.warning("Failed to navigate to comments section. Skipping.")
            continue
        
        # Extract review data
        reviews = amazon_service.extract_reviews(max_reviews, comments_in_last_n_days)
        logger.info(f"Extracted {len(reviews)} reviews")
        
        # Save reviews to CSV
        review_filename = reviews_dir / f"reviews_product_{i+1}.csv"
        amazon_service.save_reviews_to_csv(product['title'], reviews, str(review_filename))
        
        # Random delay between products
        if i < min(max_products, len(products)) - 1:
            logger.info("Taking a short break before next product...")
            random_delay(3.0, 6.0)
@print_timing
def main() -> None:
    """Main function to run the Amazon crawler"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Setup WebDriver
    driver = setup_environment(args.use_profile)
    
    try:
        # Initialize Amazon service
        amazon_service = AmazonService(driver)
        
        # Either load existing products or scrape new ones
        products = []
        if args.input_file:
            products = load_products_from_csv(args.input_file)
        else:
            products = scrape_products(amazon_service, args.search, args.output)
        
        # Process reviews if requested
        if args.reviews:
            process_product_reviews(
                amazon_service, 
                products, 
                args.max_products, 
                args.max_reviews, 
                args.comments_in_last_n_days
            )
        
        logger.info("Crawling completed successfully!")
        
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
    
    finally:
        # Close the browser
        logger.info("Closing browser...")
        driver.quit()

if __name__ == "__main__":
    main()