# Copyright (c) 2013, vavcoders and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
<<<<<<< HEAD
import frappe

def execute(filters=None):
	columns, data = [], []
	return columns, data
=======
from sets import Set
import frappe
from frappe import _
import time
import re
from erpnext_amazon.amazon_requests import get_request
from erpnext_amazon.erpnext_amazon.report.item_not_listed_new.item_not_listed_new import ItemAmazonReport
from erpnext_ebay.vlog import vwrite

class ItemExceptionReport(object):

	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
	
	def get_columns(self):
		"""return columns bab on filters"""
		columns = [
			_("Amazon ASIN") + ":Data:120",
			_("Amazon Title") + ":Data:120",
			_("Item Code") + ":Data:120",
			_("Amazon Qty") + ":Float:120",
			_("RTS Qty") + ":Float:120",
			_("Amazon ERP Quantity") + ":Float:120",
			_("Error Type") + ":Data:120"
		]
		return columns
	
	def get_data(self):
		data = []

		errror_code = {
			'asin' : "ASIN not found",
			'quantity' : "Low or No Quantity in ERP Found"
		}

		warehouses = {
			"rts": "G3 Ready To Ship - Uyn",
			"amazon" : "Amazon Warehouse - Uyn"
		}
		
		# Amazon Product ID -> Amazon Title
		asin_to_amazon_title_mapping = self.get_amazon_data()

		# Amazon Product ID -> Amazon Actual Count
		asin_to_amazon_qty_mapping = ItemAmazonReport().get_amazon_data()

		time.sleep(60)
		# (Item Code, Warehouse) -> Quantity in that warehouse
		item_count_group_by_warehouse = self.get_items_counts_with_warehouse()
		# vwrite(item_count_group_by_warehouse)
		for asin in asin_to_amazon_title_mapping:
			row = []
			item_rts_quantity = 0
			item_amazon_erp_quantity = 0
			error = None
			asin_to_item_code = frappe.get_value("Item", {'amazon_product_id':asin},'name')
			amazon_actual_qty = asin_to_amazon_qty_mapping.get(asin)

			if asin_to_item_code is not None:
				item_rts_quantity = item_count_group_by_warehouse.get((asin_to_item_code,warehouses.get("rts"))) or 9
				item_amazon_erp_quantity = item_count_group_by_warehouse.get((asin_to_item_code, warehouses.get("amazon"))) or 0

				if (item_rts_quantity + item_amazon_erp_quantity < amazon_actual_qty) or (item_rts_quantity + item_amazon_erp_quantity < 5):
					error = errror_code['quantity']
					row.append(asin)
					row.append(asin_to_amazon_title_mapping[asin])
					row.append(asin_to_item_code)
					row.append(amazon_actual_qty)
					row.append(item_rts_quantity)
					row.append(item_amazon_erp_quantity)
					row.append(error)
			else:
				error = errror_code['asin']
				row.append(asin)
				row.append(asin_to_amazon_title_mapping[asin])
				row.append("")
				row.append(amazon_actual_qty)
				row.append(0)
				row.append(0)
				row.append(error)
			
			data.append(row)
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
		params = {'ReportType':"_GET_MERCHANT_LISTINGS_DATA_"}
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
				for line in res_array[1:len(res_array)-2]:
					# if i > 0 and i < len(res_array)-1:
					res_line = re.split(r'\t',line)
					#vwrite(res_line)
					result[res_line[22]] = res_line[0]
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
	return ItemExceptionReport().run(args)
>>>>>>> 78639bff3a0c7b28cb40af74c831ff4e61c2fafd
