from __future__ import unicode_literals
import frappe
from frappe import _
from amazon.api import AmazonAPI

def get_amazon_settings():
    amazon_settings = frappe.get_doc("Amazon Settings")
    return amazon_settings

def amazon_connection(amazon_settings):
    amazon = AmazonAPI(amazon_settings.amazon_access_key, amazon_settings.amazon_secret_key,amazon_settings.amazon_assoc_tag)
    return amazon

def retrieve_images(amazon_conn, product_asin_list):
    product_asin_list = product_asin.split(',')
    for asin in product_asin_list:
        image_url_array = get_images(amazon_conn, asin)
    
    return image_url_array

def get_images(amazon_conn, product_asin):

    product = amazon_conn.lookup(ItemId = product_asin)

    return product.large_image_url