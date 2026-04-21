"""
Realistic Dataset Transformation Script
Upgrades 'Product_X' references to professional Daraz titles.
"""
import os
import re

DATASET_DIR = "dataset"

CATEGORY_MAP = {
    "Fashion > Men": "Men's Casual Wear",
    "Fashion > Women": "Women's Designer Collection",
    "Fashion > Kids": "Kids' Premium Apparel",
    "Electronics > Laptop": "High-Performance Laptop",
    "Electronics > Mobile": "SmartPhone Pro",
    "Electronics > Accessories": "Wireless Tech Accessory",
    "Beauty > Skincare": "Advanced Skin Care Serum",
    "Beauty > Makeup": "Professional Makeup Kit",
    "Shoes > Men Shoes": "Men's Athletic Shoes",
    "Shoes > Women Shoes": "Women's Fashion Heels",
    "Home Appliances > Washing Machine": "Fully Automatic Washing Machine",
    "Home Appliances > Refrigerator": "Smart Inverter Refrigerator",
    "Seller & Product Info": None, # Policy
    "Shipping & Logistics": None, # Policy
    "Returns & Refunds": None, # Policy
}

def upgrade_dataset():
    if not os.path.exists(DATASET_DIR):
        print(f"Error: {DATASET_DIR} not found.")
        return

    files = [f for f in os.listdir(DATASET_DIR) if f.endswith(".txt")]
    print(f"🔄 Processing {len(files)} files...")

    for filename in files:
        file_path = os.path.join(DATASET_DIR, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse Category & Brand
        category_match = re.search(r"Category:\s*(.*)", content)
        brand_match = re.search(r"Brand:\s*(.*)", content)
        id_match = re.search(r"Title:\s*(Product_\d+)", content)

        if not category_match or not brand_match or not id_match:
            continue # Likely a policy file

        category = category_match.group(1).strip()
        brand = brand_match.group(1).strip()
        product_id = id_match.group(1).strip() # e.g. Product_1

        item_desc = CATEGORY_MAP.get(category)
        if not item_desc:
            continue # Skip policy files

        # Generate new title: "Brand — Item Description"
        new_title = f"{brand} {item_desc}"
        
        print(f"  [UPGRADE] {product_id} -> {new_title}")

        # Replace all instances of Product_X with the new title
        # Note: We use \b to ensure we match whole words only (don't match Product_10 when looking for Product_1)
        upgraded_content = content.replace(f"Title: {product_id}", f"Title: {new_title}")
        upgraded_content = upgraded_content.replace(f"The {product_id}", f"The {new_title}")
        upgraded_content = upgraded_content.replace(f" {product_id} ", f" {new_title} ")
        
        # Cleanup any remaining Product_ identifiers in the text
        upgraded_content = upgraded_content.replace(product_id, new_title)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(upgraded_content)

    print("✅ Dataset upgrade complete.")

if __name__ == "__main__":
    upgrade_dataset()
