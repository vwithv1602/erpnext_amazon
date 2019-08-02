# Copyright (c) 2013, vavcoders and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from sets import Set
import frappe
from frappe import _
import time
import re
from erpnext_amazon.amazon_requests import get_request
from erpnext_ebay.vlog import vwrite

class ItemAmazonReport(object):

	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})

	def get_columns(self):
		"""return columns bab on filters"""
		columns = [
			_("Item Code") + ":Link/Item:120",
			_("Amazon Product ID") + ":Data:120",
			_("Flipkart Product ID") + ":Data:120",
			_("Item Group") + ":Data:120",
			_("RTS Qty") + ":Float:120",
			_("Amazon ERP Quantity") + ":Float:120",
			_("Amazon Actual Quantity") + ":Float:120",
			_("Not listed reason") + ":Data:120"
		]
		return columns
	
	def get_data(self):
		data = []
		# Mapping to (item_code,warehouse) -> count of item in that warehouse. 
		item_count_group_by_warehouse = self.get_items_counts_with_warehouse()
		item_codes = list()
		# Warehouses under 6.Ready to ship - Uyn
		warehouses = self.get_warehouse()

		# All items in warehouses including redundant item in both warehouses.
		for items in item_count_group_by_warehouse:
			item_codes.append(items[0])
		
		# Distinct itemcodes.
		item_codes = Set(item_codes)
		# Mapping item_code -> amazon product ID
		item_code_mapping = self.get_item_code_mapping_to_asin()

		# Item Code -> FBA count
		item_amazon_count_mapping = self.get_amazon_data()

		for item_code in item_codes:
			amazon_erp_qty = 0
			rts_qty = 0
			item_group = frappe.db.get_value("Item",{'name':item_code},'item_group')
			for warehouse in warehouses:
				# for (k,v) in item_count_group_by_warehouse.iteritems():
				if (item_code,warehouse) in item_count_group_by_warehouse:
					if "Ready" in warehouse:
						rts_qty = item_count_group_by_warehouse.get((item_code,warehouse))
					
					if "Amazon" in warehouse:
						amazon_erp_qty = item_count_group_by_warehouse.get((item_code,warehouse))
			
			amazon_actual_qty = 0
			asin = self.get_asin_from_erp(item_code)
			fsin = self.get_fsin_from_erp(item_code)
			amazon_actual_qty = item_amazon_count_mapping.get(item_code) or 0
			if ((rts_qty + amazon_erp_qty + amazon_actual_qty) == 0) or (rts_qty == 0 and amazon_erp_qty == amazon_actual_qty):
				continue
			item_not_listed_reason = self.get_not_listing_reason(item_code)
			data.append([str(item_code), asin, fsin, item_group,int(rts_qty),amazon_erp_qty,amazon_actual_qty,item_not_listed_reason])
		# return []
		data.sort(key=lambda x: (x[4]+x[5]-x[6]),reverse=True)
		return data

	def get_warehouse(self):
		warehouse_query = '''select name from `tabWarehouse` where parent_warehouse like "6. Ready to ship - Uyn"'''
		warehouses = []
		for warhouse in frappe.db.sql(warehouse_query,as_dict=1):
			warehouses.append(str(warhouse.get("name")).strip())
		return warehouses

	def get_asin_from_erp(self, item_code):
		asin = frappe.get_value("Item", item_code,"amazon_product_id")
		return asin
	
	def get_fsin_from_erp(self, item_code):
		fsin = frappe.get_value("Item", item_code,"flipkart_product_id")
		return fsin

	def get_items_counts_with_warehouse(self):
		item_count_group_by_warehouse_query = """select i.item_code,sn.warehouse,count(sn.name) from `tabSerial No` sn inner join `tabItem` i on i.item_code=sn.item_code where sn.warehouse in (select name from `tabWarehouse` where parent_warehouse like "6. Ready to ship - Uyn") group by i.item_code,sn.warehouse;"""
		item_count_group_by_warehouse = {}
		for item_list in frappe.db.sql(item_count_group_by_warehouse_query):
			item_count_group_by_warehouse[ (str(item_list[0]), str(item_list[1])) ] = int(str(item_list[2]))
		return item_count_group_by_warehouse

	def get_item_code_mapping_to_asin(self):
		item_code_mapping_query = '''select name,amazon_product_id from `tabItem` where amazon_product_id is not null and amazon_product_id != ""'''	
		item_code_mapping = {}
		for item in frappe.db.sql(item_code_mapping_query, as_dict=1):
			item_code_mapping[str(item['name'])] = str(item['amazon_product_id'])

		return item_code_mapping
	
	def get_amazon_data(self):
		result = {}
		all_items_with_asins_query = """select name, amazon_available_quantity, amazon_reserved_quantity from `tabItem` where amazon_product_id is not null and amazon_product_id != ''"""
		all_items_with_asins_dict = frappe.db.sql(all_items_with_asins_query,as_dict=1)
		for lines in all_items_with_asins_dict:
			result[lines.get('name')] = int(lines.get('amazon_available_quantity')) + int(lines.get('amazon_reserved_quantity'))
		return result
		
	def get_not_listing_reason(self,item_code):
		item_reason = frappe.get_value("Item",item_code, "not_listing_reason")
		if not item_reason:
			return ""
		else:
			return item_reason

	def run(self, args):
		columns = self.get_columns()
		data = self.get_data()
		return columns,data#, data

def execute(filters=None):
	args = {}
	return ItemAmazonReport().run(args)
