# Copyright (c) 2013, vavcoders and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from sets import Set
import frappe
from frappe import _
import time
import datetime
import re
from erpnext.stock.stock_balance import get_balance_qty_from_sle
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
			_("Item Code") + ":Data:340",
			_("Amazon Available Qty") + ":Float:120",
			_("Amazon Reserved Qty") + ":Float:120",
			_("Packed") + ":Float:120",
			_("RTS Qty") + ":Float:120",
			_("Amazon ERP Quantity") + ":Float:120",
			_("Not Listing Reason") + ":Data:120"
		]
		return columns
	
	def get_data(self):
		data = []

		warehouses = {
			"rts": "G3 Ready To Ship - Uyn",
			"amazon" : "Amazon Warehouse - Uyn"
		}
		

		# item code -> Amazon Actual Count
		item_to_amazon_qty_mapping = self.get_amazon_data()
		
		# Amazon Product ID -> Amazon Title
		asin_to_amazon_title_mapping = self.get_amazon_active_listing()
		
		# (Item Code, Warehouse) -> Quantity in that warehouse
		item_count_group_by_warehouse = self.get_items_counts_with_warehouse()

		encode_to_utf = lambda a: a.encode('utf-8').strip()


		
		# vwrite(item_count_group_by_warehouse)
		for asin in asin_to_amazon_title_mapping:
			row = []
			not_listing_reason = []
			item_rts_quantity = 0
			item_amazon_erp_quantity = 0
			packed_no = 0
			asin_to_item_code_query = """select name from `tabItem` where amazon_product_id like '%%{0}%%'""".format(asin)
			asin_to_item_code = frappe.db.sql(asin_to_item_code_query, as_list=1)
			item_code = None
			if asin_to_item_code:
				if len(asin_to_item_code[0]) > 0:
					item_code = asin_to_item_code[0][0]
			
			if item_code:
				amazon_available_qty,amazon_reserved_qty = item_to_amazon_qty_mapping.get(item_code)
				amazon_actual_qty = amazon_available_qty + amazon_reserved_qty
			else:
				amazon_actual_qty = 0
				amazon_available_qty = 0
				amazon_reserved_qty = 0

			if amazon_actual_qty > 0:
				if asin_to_item_code:
					for item in asin_to_item_code:
						item_code = item[0]
						packed_no += self.item_code_to_delivery_note_count(item_code)
						reason = frappe.db.get_value('Item',{'name':item_code},'not_listing_reason')
						if reason:
							not_listing_reason.append(reason)
						item_rts_quantity += (item_count_group_by_warehouse.get((item_code,warehouses.get("rts"))) or 0)
						item_amazon_erp_quantity += (item_count_group_by_warehouse.get((item_code, warehouses.get("amazon"))) or 0)

					if (item_rts_quantity + item_amazon_erp_quantity < 5) and (item_rts_quantity + item_amazon_erp_quantity + packed_no < amazon_actual_qty):
						row.append(encode_to_utf(asin))
						row.append(encode_to_utf(asin_to_amazon_title_mapping[asin]))
						row.append(encode_to_utf(item_code))
						row.append(amazon_available_qty)
						row.append(amazon_reserved_qty)
						row.append(packed_no)
						row.append(item_rts_quantity)
						row.append(item_amazon_erp_quantity)
						row.append('\n'.join(not_listing_reason))
					if row:
						data.append(row)
				else:
					row.append(encode_to_utf(asin))
					row.append(encode_to_utf(asin_to_amazon_title_mapping[asin]))
					row.append(encode_to_utf(""))
					row.append(amazon_available_qty)
					row.append(amazon_reserved_qty)
					row.append(0)
					row.append(0)
					row.append(0)
					row.append("")
					data.append(row)
				#vwrite(row)
				
		#vwrite(data)
		return data

	def item_code_to_delivery_note_count(self,item_code):
		yesterday = str(datetime.date.today() - datetime.timedelta(1))
		count_query = """select count(*) from `tabDelivery Note` as dn inner join `tabDelivery Note Item` as dni on dn.name = dni.parent where dni.item_code='{0}' and dn.docstatus = 1 and dn.is_return = 0 and dn.creation > '{1} 14:00:00.0000'""".format(item_code, yesterday)
		total_count = frappe.db.sql(count_query,as_list = 1)
		return total_count[0][0]

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
		result = {}
		all_items_with_asins_query = """select name,amazon_available_quantity,amazon_reserved_quantity from `tabItem` where amazon_product_id is not null and amazon_product_id != ''"""
		all_items_with_asins_dict = frappe.db.sql(all_items_with_asins_query,as_dict=1)
		for lines in all_items_with_asins_dict:
			result[lines.get('name')] = (int(lines.get('amazon_available_quantity')), int(lines.get('amazon_reserved_quantity')))
		return result
	
	def get_amazon_active_listing(self):
		params = {'ReportType':"_GET_MERCHANT_LISTINGS_DATA_"}
		report_result = get_request('request_report', params)
		i = 0
		amazon_prod_ids = []
		result = {}
		encode_to_utf = lambda a: a.encode('utf-8').strip()
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
					try:
						result[res_line[22]] = encode_to_utf(res_line[0]).strip()
					except:
						result[res_line[22]] = "Contains non Ascii character"
				i = i+1
				break
			else:
				#vwrite("Submission processing error. Quit.")
				break
			if i == 3:
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
