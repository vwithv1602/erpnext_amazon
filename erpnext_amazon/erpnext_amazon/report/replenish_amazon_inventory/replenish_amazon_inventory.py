# Copyright (c) 2013, vavcoders and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
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
			_("Item Code") + ":Link/Item:240",
			_("RTS Qty") + ":Float:60",
			_("Amazon ERP Quantity") + ":Float:60",
			_("Amazon Actual Quantity") + ":Float:60",
			_("Amazon Reserved Quantity") + ":Float:60",
			_("Amazon Product ID") + ":Data:120"
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

		# Mapping amazon product ID -> FBA count, reserved Quantity
		amazon_asin_count_mapping = self.get_amazon_data()
		vwrite(amazon_asin_count_mapping)

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
			brand = frappe.get_value("Item",{"name":item_code},"brand")
			amazon_actual_qty = self.get_amazon_count(item_code, item_code_mapping, amazon_asin_count_mapping)
			if (rts_qty + amazon_erp_qty > amazon_actual_qty) and (amazon_actual_qty < 3) and (asin is not None) and (asin != "") and (brand != "Apple"):
				data.append([str(item_code), int(rts_qty),amazon_erp_qty,amazon_actual_qty[0],amazon_actual_qty[1],asin])
		# return []
		return data

	def get_amazon_count(self, item_code, item_code_mapping, amazon_asin_count_mapping):
		amazon_actual_qty = 0
		if item_code in item_code_mapping:
			asin_list_str = item_code_mapping.get(item_code)
			asin_list = asin_list_str.split(',')
			for asin in asin_list:
				if asin in  amazon_asin_count_mapping:
					amazon_actual_qty += int(amazon_asin_count_mapping.get(asin))
		return amazon_actual_qty

	def get_warehouse(self):
		warehouse_query = '''select name from `tabWarehouse` where parent_warehouse like "6. Ready to ship - Uyn"'''
		warehouses = []
		for warhouse in frappe.db.sql(warehouse_query,as_dict=1):
			warehouses.append(str(warhouse.get("name")).strip())
		return warehouses

	def get_asin_from_erp(self, item_code):
		asin = frappe.get_value("Item", item_code,"amazon_product_id")
		return asin
	
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
		params = {'ReportType':"_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_"}
		report_result = get_request('request_report', params)
		i = 0
		amazon_prod_ids = []
		result = {}
		while True:
			i = i+1
			params = {'ReportRequestIdList':[report_result.RequestReportResult.ReportRequestInfo.ReportRequestId]}
			submission_list = get_request('get_report_request_list',params)
			info =  submission_list.GetReportRequestListResult.ReportRequestInfo[0]
			id = info.ReportRequestId
			status = info.ReportProcessingStatus
			#vwrite('Submission Id: {}. Current status: {}'.format(id, status))
			
			if (status in ('_SUBMITTED_', '_IN_PROGRESS_', '_UNCONFIRMED_')):
				#vwrite('Sleeping for 5s and check again....')
				time.sleep(5)
			elif (status == '_DONE_'):
				generated_report_id = info.GeneratedReportId
				reportResult = get_request('get_report',{'ReportId':generated_report_id})
				res_array = re.split(r'\n+', reportResult)
				i = 0
				#vwrite(res_array)
				for line in res_array[1:]:
					# if i > 0 and i < len(res_array)-1:
					res_line = re.split(r'\t+', line)
					if res_line[3] == 'Unknown' or res_line[4] == 'Unknown':
						continue
					result[res_line[2]] = (int(res_line[9]), int(res_line[11]))
					amazon_prod_ids.append(res_line[1])
				i = i+1
				break
			else:
				#vwrite("Submission processing error. Quit.")
				break
			if i > 5:
				#vwrite("Increment crossed 10")
				break
		return result

	def run(self, args):
		columns = self.get_columns()
		data = self.get_data()
		return columns,data#, data

def execute(filters=None):
	args = {}
	return ItemAmazonReport().run(args)