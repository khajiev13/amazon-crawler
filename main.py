#!/usr/bin/env python3
"""
Amazon Smart TV Web Crawler Main Script
This script uses Selenium to search for smart TVs on Amazon and extract product information.
"""
import argparse
import csv
import os
from typing import Any, Dict, List
from utils.driver_utils import setup_driver, random_delay, human_like_scroll
from services.amazon_service import AmazonService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver import Keys
import time

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Amazon Smart TV Crawler")
    parser.add_argument("--search", type=str, default="smart tvs", 
                      help="Search term to use (default: 'smart tvs')")
    parser.add_argument("--output", type=str, default="amazon_smarttvs.csv",
                      help="Output CSV filename (default: amazon_smarttvs.csv)")
    parser.add_argument("--reviews", action="store_true",
                      help="Scrape product reviews (default: False)")
    parser.add_argument("--max-products", type=int, default=5,
                      help="Maximum number of products to process for reviews (default: 5)")
    parser.add_argument("--max-reviews", type=int,
                      help="Maximum number of reviews per product to collect (default: 10)")
    parser.add_argument("--input-file", type=str,
                      help="Input CSV file with product links (if already scraped)")
    parser.add_argument("--use-profile", action="store_true", 
                      help="Use your existing Chrome profile with saved logins (default: False)")
    parser.add_argument("--comments-in-last-n-days", type=int,
                      help="Number of days to consider for comments")
    return parser.parse_args()

def main():
    """Main function to run the Amazon crawler"""
    # Parse command line arguments
    args = parse_arguments()
    search_term = args.search
    output_file = args.output
    scrape_reviews = args.reviews
    max_products = args.max_products
    max_reviews = args.max_reviews
    input_file = args.input_file
    use_profile = args.use_profile
    comments_in_last_n_days = args.comments_in_last_n_days
    
    
    
    # Setup the WebDriver with user profile if requested
    if use_profile:
        print("Using your existing Chrome profile with saved logins")
        driver = setup_driver(use_profile=True)
    else:
        driver = setup_driver()
    
    try:
        # Initialize Amazon service
        amazon_service = AmazonService(driver)
        
        # If an input file is provided, load products from there
        products = []
        if input_file and os.path.exists(input_file):
            print(f"Loading products from {input_file}")
            with open(input_file, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                products = list(reader)
            print(f"Loaded {len(products)} products from CSV")
        else:
            print(f"Starting Amazon crawler with search term: '{search_term}'")
            print(f"Results will be saved to: {output_file}")
            # Navigate to Amazon and perform search
            if not amazon_service.perform_search(search_term):
                print("Failed to perform search. Exiting.")
                return
            
            random_delay()
            
            
            # Extract product data
            print("Extracting product data...")
            products = amazon_service.extract_product_data()
            
            print(f"Found {len(products)} products.")
            
            # Save data to CSV
            amazon_service.save_to_csv(products, output_file)
        
        # Process reviews if requested
        if scrape_reviews and products:
            print(f"Starting to collect reviews for up to {max_products} products...")
            
            # Create a reviews directory if it doesn't exist
            reviews_dir = "reviews"
            os.makedirs(reviews_dir, exist_ok=True)
            
            # Process each product (limiting to max_products)
            for i, product in enumerate(products[:max_products]):
                print(f"\nProcessing product {i+1}/{min(max_products, len(products))}")
                print(f"Title: {product['title'][:50]}...")
                
                # # Visit the product detail page
                # if not amazon_service.visit_product_details(product['link']):
                #     print("Failed to load product page. Skipping.")
                #     continue
                
                # # Navigate to reviews section
                # if not amazon_service.navigate_to_reviews():
                #     print("Failed to navigate to reviews section. Skipping.")
                #     continue

                # Navigate to comments using asin
                if not amazon_service.navigate_to_reviews_by_asin(product['asin']):
                    print("Failed to navigate to comments section. Skipping.")
                    continue
                
                # Extract review data
                reviews = amazon_service.extract_reviews(max_reviews,comments_in_last_n_days)
                print(f"Extracted {len(reviews)} reviews")
                
                # Save reviews to CSV
                review_filename = os.path.join(reviews_dir, f"reviews_product_{i+1}.csv")
                amazon_service.save_reviews_to_csv(product['title'], reviews, review_filename)
                
                # Random delay between products
                if i < min(max_products, len(products)) - 1:
                    print("Taking a short break before next product...")
                    random_delay(3.0, 6.0)
        
        print("Crawling completed successfully!")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Close the browser
        print("Closing browser...")
        driver.quit()

if __name__ == "__main__":
    main()