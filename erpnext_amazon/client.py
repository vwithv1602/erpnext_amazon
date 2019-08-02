# Copyright (c) 2013, vavcoders and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from sets import Set
import frappe
from frappe import _
import time
import datetime
import re
from frappe.utils.background_jobs import enqueue
from .amazon_requests import get_request
from erpnext_ebay.vlog import vwrite

@frappe.whitelist()
def sync_amazon_quantity():
    enqueue("erpnext_amazon.client.update_item_list_amazon_qty", queue='long')
    frappe.msgprint(_("Queued for syncing. It may take a few minutes to an hour if this is your first sync."))

def update_item_list_amazon_qty():
    item_code_mapping_to_asin = get_item_code_mapping_to_asin()
    asin_to_amazon_qty_mapping = get_amazon_data()

    for item in item_code_mapping_to_asin:
        item_available_qty = 0
        item_reserved_qty = 0
        asin_list = item_code_mapping_to_asin[item].split(',')
        for asin in asin_list:
            if asin in asin_to_amazon_qty_mapping:
                item_available_qty += asin_to_amazon_qty_mapping.get(asin)[0]
                item_reserved_qty += asin_to_amazon_qty_mapping.get(asin)[1]
        update_query = """update `tabItem` set amazon_available_quantity='{0}',amazon_reserved_quantity='{1}' where name = '{2}'""".format(item_available_qty,item_reserved_qty,item)
        try:
            frappe.db.sql(update_query)   
            frappe.db.commit()
        except:
            vwrite("Failed updation for the query.")
            vwrite(update_query)

def get_item_code_mapping_to_asin():
    item_code_mapping_query = '''select name,amazon_product_id from `tabItem` where amazon_product_id is not null and amazon_product_id != ""'''	
    item_code_mapping = {}
    for item in frappe.db.sql(item_code_mapping_query, as_dict=1):
        item_code_mapping[str(item['name'])] = str(item['amazon_product_id'])

    return item_code_mapping

def get_amazon_data():
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
            for line in res_array[1:]:
                # if i > 0 and i < len(res_array)-1:
                res_line = re.split(r'\t+', line)
                if (res_line[3] == 'Unknown') or (res_line[4] == 'Unknown'):
                    continue
                result[res_line[2]] = (int(res_line[9]),int(res_line[11]))
            i = i+1
            break
        else:
            #vwrite("Submission processing error. Quit.")
            break
        if i > 5:
            #vwrite("Increment crossed 10")
            break
    return result

	
	