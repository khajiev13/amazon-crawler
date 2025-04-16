#!/usr/bin/env python3
"""
Amazon data models using Pydantic
Defines structured data types for Amazon product reviews and related data
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ReviewImage(BaseModel):
    """Model for a review image"""
    thumbnail_url: str
    full_size_url: str


class Review(BaseModel):
    """Model for an Amazon product review"""
    customer_name: str = Field(default="N/A")
    country: str = Field(default="N/A")
    date: str = Field(default="N/A")
    title: str = Field(default="N/A")
    rating: str = Field(default="N/A")
    text: str = Field(default="N/A")
    images: List[ReviewImage] = Field(default_factory=list)
    verified_purchase: bool = Field(default=False)
    helpful_count: int = Field(default=0)
    
    @field_validator('rating')
    def validate_rating(cls, v):
        """Convert rating to consistent format if possible"""
        try:
            # If it's a digit, ensure it's a string
            if v.isdigit():
                return v
            # Try to extract number from formats like "4.5 out of 5"
            if "out of" in v:
                return v.split("out of")[0].strip()
        except (ValueError, AttributeError):
            pass
        return v


class Product(BaseModel):
    """Model for an Amazon product"""
    title: str
    link: str
    asin: Optional[str] = None
    
    @field_validator('asin', mode='before')
    def extract_asin(cls, v, values):
        """Extract ASIN from link if not provided"""
        if not v and 'link' in values:
            link = values['link']
            if '/dp/' in link:
                try:
                    return link.split('/dp/')[1].split('/')[0]
                except:
                    pass
        return v
    

class CustomerSentiment(BaseModel):
    """Model for AI-generated customer sentiment about a product"""
    summary: str = Field(default="N/A")
    positive_aspects: List[Review] = Field(default_factory=list)
    negative_aspects: List[Review] = Field(default_factory=list)
    mixed_aspects: List[Review] = Field(default_factory=list)
    
    @field_validator('positive_aspects', 'negative_aspects', 'mixed_aspects', mode='before')
    def ensure_list(cls, v):
        """Ensure the value is a list"""
        if isinstance(v, str):
            return [aspect.strip() for aspect in v.split(',')]
        return v


class FilteredProducts(Product):
    """Model for filtered product information with technical specifications"""
    brand_name: str = Field(default="N/A")
    item_weight: str = Field(default="N/A")
    product_dimensions: str = Field(default="N/A")
    country_of_origin: str = Field(default="N/A")
    item_model_number: str = Field(default="N/A")
    color: str = Field(default="N/A")
    special_features: List[str] = Field(default_factory=list)
    screen_size: str = Field(default="N/A")
    aspect_ratio: str = Field(default="N/A")
    resolution: str = Field(default="N/A")
    connectivity_technology: str = Field(default="N/A")
    refresh_rate: str = Field(default="N/A")
    display_technology: str = Field(default="N/A")
    mounting_type: str = Field(default="N/A")
    price: str = Field(default="N/A")
    ratings_count: int = Field(default=0)
    average_rating: float = Field(default=0.0)
    customer_sentiment: Optional[CustomerSentiment] = None

    @field_validator('special_features', mode='before')
    def split_features(cls, v):
        """Split comma-separated features into a list"""
        if isinstance(v, str):
            return [feature.strip() for feature in v.split(',')]
        return v
