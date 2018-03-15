import frappe
from frappe import _
import json, math, time
from .exceptions import AmazonError
from vlog import vwrite

def get_amazon_category_id_of_item(item):
    vwrite("getting amazon category id")
    category_id_query = """select amazon_category_id from `tabItem Group` where name='%s'""" % (item.get("item_group"))
    vwrite(category_id_query)
    category_id = None
    for category_id_row in frappe.db.sql(category_id_query, as_dict=1):
        category_id = category_id_row.get("amazon_category_id")
    return category_id
def get_oldest_serial_number(amazon_product_id):
    oldest_serial_number = None
    serial_number_query = """select sn.name,sn.serial_no,sn.item_code from `tabSerial No` sn inner join tabItem i on i.item_code=sn.item_code where i.amazon_product_id='%s' or i.amazon_product_id like '%s' or i.amazon_product_id like '%s' or i.amazon_product_id like '%s' order by sn.creation limit 1""" % (amazon_product_id,amazon_product_id+",%","%,"+amazon_product_id+",%","%,"+amazon_product_id)
    for serial_number in frappe.db.sql(serial_number_query, as_dict=1):
        oldest_serial_number = serial_number.get("serial_no")
    return oldest_serial_number
def get_amazon_item_specifics(item):
    vwrite(item)
    vwrite("^^^^^^Item^^^^^^")
    return False
    item_specifics = []
    if (get_amazon_category_id_of_item(item)=='15032'):
        item_specifics = [
                    {
                        "Name": "Brand",
                        "Value": "Samsung"
                    },
                    {
                        "Name": "Model",
                        "Value": "G4 Play"
                    },
                    {
                        "Name": "MPN",
                        "Value": "Does Not Apply"
                    },
                    {
                        "Name": "Operating System",
                        "Value": "Android"
                    },
                    {
                        "Name": "Colour",
                        "Value": "Black"
                    },
                    {
                        "Name": "Sim Type",
                        "Value": "Dual SIM"
                    },
                    {
                        "Name": "Operating System Version Name",
                        "Value": "Jelly Bean"
                    },
                    {
                        "Name": "Processor",
                        "Value": "Single Core"
                    },
                    {
                        "Name": "RAM",
                        "Value": "2 GB"
                    },
                    {
                        "Name": "Screen Size",
                        "Value": "50"
                    },
                    {
                        "Name": "Storage Capacity",
                        "Value": "1 GB and Below"
                    },
                    {
                        "Name": "Storage Capacity(Internal)",
                        "Value": "1 GB and Below"
                    },

                    {
                        "Name": "Primary Camera",
                        "Value": "8.0 MP"
                    },
                    {
                        "Name": "Secondary Camera",
                        "Value": "5.0 MP"
                    },
                    {
                        "Name": "Warranty",
                        "Value": "No Warranty"
                    },
                    {
                        "Name": "Duration",
                        "Value": "6 months"
                    },
                    {
                        "Name": "Battery Capacity",
                        "Value": "2800mAh"
                    },
                    {
                        "Name": "Network Type",
                        "Value": "3G and 4G"
                    }
                ]
    elif (get_amazon_category_id_of_item(item)=='172312'): # for TV
        item_specifics = [
                    {
                        "Name": "Brand",
                        "Value": "Samsung"
                    },
                    {
                        "Name": "Network Type",
                        "Value": "3G and 4G"
                    }
                ]

    return item_specifics