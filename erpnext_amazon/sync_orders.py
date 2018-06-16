from __future__ import unicode_literals
from datetime import datetime,timedelta
import frappe
from frappe import _
from .exceptions import AmazonError
from .utils import make_amazon_log
import frappe
from .sync_products import update_qty_in_amazon_site,get_sku_of_item
from .sync_customers import create_customer,create_customer_address,create_customer_contact
from frappe.utils import flt, nowdate, cint
from .amazon_item_common_functions import get_oldest_serial_number
from .amazon_requests import get_request
from vlog import vwrite

from parse_erpnext_connector.parse_orders import parse_order

amazon_settings = frappe.get_doc("Amazon Settings", "Amazon Settings")
if amazon_settings.last_sync_datetime:
    startTimeString = amazon_settings.last_sync_datetime
    startTimeString = startTimeString[:19]
    startTimeObj = datetime.strptime(startTimeString, '%Y-%m-%d %H:%M:%S')
    startTime = (startTimeObj + timedelta(-1)).isoformat()
else:
    startTime = (datetime.now() + timedelta(-1)).isoformat()
endTime = datetime.now().isoformat()

def sync_orders():
    sync_amazon_orders()
def get_amazon_orders(ignore_filter_conditions=False):
    amazon_orders = []
    params = {}
    amazon_orders = get_request('list_orders', params)
    return amazon_orders.ListOrdersResult.Orders.Order
def check_amazon_sync_flag_for_item(amazon_product_id):
    sync_flag = False
    sync_flag_query = """select sync_with_amazon from tabItem where amazon_product_id='%s' or amazon_product_id like '%s' or amazon_product_id like '%s' or amazon_product_id like '%s'""" % (amazon_product_id,amazon_product_id+",%","%,"+amazon_product_id+",%","%,"+amazon_product_id)
    try:
        for item in frappe.db.sql(sync_flag_query, as_dict=1):
            if item.get("sync_with_amazon"):
                sync_flag = True
            else:
                sync_flag = False
    except Exception, e:
        vwrite("Exception raised in check_amazon_sync_flag_for_item")
        vwrite(e)
    return sync_flag
def sync_amazon_orders():
    frappe.local.form_dict.count_dict["orders"] = 0
    get_amazon_orders_array = get_amazon_orders()
    if not len((get_amazon_orders_array)):
        return False
    for amazon_order in get_amazon_orders_array:
        amazon_order_with_item_details = []
        # call api for items by sending amazon_order.AmazonOrderId
        params = {'AmazonOrderId':amazon_order.AmazonOrderId}
        list_order_items = get_request('list_order_items', params)
        amazon_order_with_item_details.append(amazon_order)
        amazon_order_with_item_details.append(list_order_items)
        parsed_order = parse_order("amazon",amazon_order_with_item_details)
        if parsed_order:
            amazon_item_id = parsed_order.get("item_details").get("item_id")
            is_item_in_sync = check_amazon_sync_flag_for_item(amazon_item_id)
            if(is_item_in_sync):
                if valid_customer_and_product(parsed_order):
                    try:
                        create_order(parsed_order, amazon_settings)
                        frappe.local.form_dict.count_dict["orders"] += 1

                    except AmazonError, e:
                        vwrite("AmazonError raised in create_order")
                        vwrite(amazon_order)
                        make_amazon_log(status="Error", method="sync_amazon_orders", message=frappe.get_traceback(),
                                        request_data=amazon_order.get("OrderID"), exception=True)
                    except Exception, e:
                        vwrite("Exception raised in create_order")
                        vwrite(e)
                        vwrite(parsed_order)
                        if e.args and e.args[0]:
                            raise e
                        else:
                            make_amazon_log(title=e.message, status="Error", method="sync_amazon_orders",
                                            message=frappe.get_traceback(),
                                            request_data=amazon_order.get("OrderID"), exception=True)
                else:
                    vwrite("Not valid customer and product")
            else:
                vwrite("Item not in sync: %s" % amazon_item_id)
                make_amazon_log(title="%s" % amazon_item_id, status="Error", method="sync_amazon_orders", request_data=amazon_order.get("OrderID"),message="Sales order item is not in sync with erp. Sales Order: %s " % amazon_order.get("OrderID"))
        else:
            vwrite("Parsing failed")
            make_amazon_log(title="%s" % amazon_order.AmazonOrderId, status="Error", method="sync_amazon_orders",
                                request_data=amazon_order,message="Parsing failed for Sales Order: %s " % amazon_order.AmazonOrderId)
def sync_amazon_qty():
    # items_sql = """ select * from tabItem where sync_with_amazon='1' and sync_qty_with_amazon='1' and item_code='Refurbished Lenovo Thinkpad T410 Core I5 2 GB 320 GB Black' """
    items_sql = """ select distinct item_code,amazon_product_id,variant_of from tabItem where sync_with_amazon='1' and sync_qty_with_amazon='1' and has_variants='0' """
    items_res = frappe.db.sql(items_sql, as_dict=1)
    update_data = []
    for amazon_item in items_res:
        item_code = amazon_item.get("item_code")
        if not amazon_item.get("variant_of"): # for non-variant items
            qty_to_be_updated = get_balance_qty_in_erp(item_code)
            if amazon_item.get("amazon_product_id"):
                for amazon_product_id in amazon_item.get("amazon_product_id").split(','):
                    if qty_to_be_updated<0:
                        qty_to_be_updated = 0
                    is_MFN = is_fulfillment_by_merchant(amazon_product_id)
                    if is_MFN:
                        update_data.append({'amazon_product_id':amazon_product_id,'qty_to_be_updated':qty_to_be_updated})
                    # update_qty_in_amazon_site(amazon_product_id,qty_to_be_updated)
        else: # for variant items
            qty_to_be_updated = get_balance_qty_in_erp_for_variant_item(item_code)
    update_qty_in_amazon_site(update_data)

def is_fulfillment_by_merchant(amazon_product_id):
    sku = get_sku_of_item(amazon_product_id)
    params = {'SellerSkus':get_sku_of_item(amazon_product_id)}
    item_info = get_request('list_inventory_supply',params)
    try:
        FBA = None
        FBA = item_info.ListInventorySupplyResult.InventorySupplyList[0].ASIN
        if FBA:
            return False
    except Exception, e:
        return True
def get_balance_qty_in_erp(item_code):
    stock_sql = """ select sum(actual_qty) as bal_qty from `tabStock Ledger Entry` where warehouse like '%s' and item_code='%s' """ %  (amazon_settings.warehouse[:-6]+'%',item_code)
    stock_res = frappe.db.sql(stock_sql, as_dict=1)
    if stock_res[0] and stock_res[0].get("bal_qty"):
        bal_qty = stock_res[0].get("bal_qty")
    else:
        bal_qty = 0
    so_submitted_sql = """ select sum(soi.qty) as so_submitted_qty from `tabSales Order` so inner join `tabSales Order Item` soi on soi.parent = so.name where soi.item_code='%s' and so.status not in ('Draft','Closed','Cancelled','Completed') """ % item_code
    so_submitted_res = frappe.db.sql(so_submitted_sql, as_dict=1)
    if so_submitted_res[0] and so_submitted_res[0].get("so_submitted_qty"):
        so_submitted_count = so_submitted_res[0].get("so_submitted_qty")
    else:
        so_submitted_count = 0
    actual_qty = bal_qty - so_submitted_count
    return actual_qty
def get_balance_qty_in_erp_for_variant_item(item_code):
    # vwrite("variant Item logic for %s" % item_code)
    return True
def valid_customer_and_product(parsed_order):
    amazon_order = None
    customer_id = parsed_order.get("customer_details").get("buyer_id")
    if customer_id:
        if not frappe.db.get_value("Customer", {"amazon_customer_id": customer_id}, "name"):
            create_customer(parsed_order, amazon_customer_list=[])
        else:
            create_customer_address(parsed_order, customer_id)
            create_customer_contact(parsed_order, customer_id)

    else:
        raise _("Customer is mandatory to create order")

    warehouse = frappe.get_doc("Amazon Settings", "Amazon Settings").warehouse
    return True
    for item in amazon_order.get("line_items"):
        if not frappe.db.get_value("Item", {"amazon_product_id": item.get("product_id")}, "name"):
            item = get_request("/admin/products/{}.json".format(item.get("product_id")))["product"]
            make_item(warehouse, item, amazon_item_list=[])

    return True


def create_order(parsed_order, amazon_settings, company=None):
    so = create_sales_order(parsed_order, amazon_settings, company)
    # if amazon_order.get("financial_status") == "paid" and cint(amazon_settings.sync_sales_invoice):
    #     create_sales_invoice(amazon_order, amazon_settings, so)
    #
    # if amazon_order.get("fulfillments") and cint(amazon_settings.sync_delivery_note):
    #     create_delivery_note(amazon_order, amazon_settings, so)

def create_sales_order(parsed_order, amazon_settings, company=None):
    so = frappe.db.get_value("Sales Order", {"amazon_order_id": parsed_order.get("order_details").get("order_id")}, "name")
    if not so:
        transaction_date = datetime.strptime(nowdate(), "%Y-%m-%d")
        delivery_date = transaction_date + timedelta(days=4)
        # get oldest serial number and update in tabSales Order
        serial_number = get_oldest_serial_number(parsed_order.get("item_details").get("item_id")) # sending amazon_product_id
        try:
            if parsed_order.get("order_details").get("payment_method")=='COD':
                is_cod = True
            else:
                is_cod = False
            if 'fulfillment_channel' in parsed_order.get("order_details"):
                fulfillment_channel = parsed_order.get("order_details").get("fulfillment_channel")
            else:
                fulfillment_channel = ""
            if parsed_order.get("order_details").get("is_amazon_replacement")=='true':
                is_amazon_replacement = True
            else:
                is_amazon_replacement = False
            so = frappe.get_doc({
                "doctype": "Sales Order",
                "naming_series": amazon_settings.sales_order_series or "SO-Amazon-",
                "is_cod": is_cod,
                "amazon_order_id": parsed_order.get("order_details").get("order_id"),
		"amazon_buyer_id": parsed_order.get("customer_details").get("buyer_id"),
                "customer": frappe.db.get_value("Customer",
                                                {"amazon_customer_id": parsed_order.get("customer_details").get("buyer_id")}, "name"),
                "delivery_date": delivery_date,
                "transaction_date": parsed_order.get("order_details").get("order_date")[:10],
                "company": amazon_settings.company,
                "selling_price_list": amazon_settings.price_list,
                "ignore_pricing_rule": 1,
                "items": get_order_items(parsed_order.get("item_details").get("all_items"), amazon_settings),                
                "item_serial_no": serial_number,
                "fulfillment_channel": fulfillment_channel,
                "is_amazon_replacement":is_amazon_replacement
                # "taxes": get_order_taxes(amazon_order.get("TransactionArray").get("Transaction"), amazon_settings),
                # "apply_discount_on": "Grand Total",
                # "discount_amount": get_discounted_amount(amazon_order),
            })
            if "Certified Refurbished" in so.__dict__.get("items")[0].__dict__.get("item_name"):
                so.update({
                    "mail_to_amazon_buyer":1
                })
            if company:
                so.update({
                    "company": company,
                    "status": "Draft"
                })
            so.flags.ignore_mandatory = True
            try:
                so.save(ignore_permissions=True)
            except Exception, e:
                vwrite("in exception")
                vwrite(e)
            return False
            if(parsed_order.get("order_details").get("parent_order_id") != 0):
                # variation_details = get_variation_details(amazon_order.get("TransactionArray").get("Transaction")[0])
                variation_details = parsed_order.get("order_details").get("parent_order_id") # yet to find variation details parameter in amazon
                created_so_id = frappe.db.get_value("Sales Order",{"amazon_order_id": parsed_order.get("order_details").get("order_id")}, "name")
                update_wrnty_in_desc_query = """ update `tabSales Order Item` set description='%s' where parent='%s'""" % (variation_details,created_so_id)
                update_wrnty_in_desc_result = frappe.db.sql(update_wrnty_in_desc_query, as_dict=1)
            # so.submit()
        except AmazonError, e:
            vwrite("AmazonError raised in create_sales_order")
            vwrite(parsed_order)
            make_amazon_log(title=e.message, status="Error", method="create_sales_order", message=frappe.get_traceback(),
                          request_data=parsed_order.get("order_details").get("order_id"), exception=True)
        except Exception, e:
            vwrite("Exception raised in create_sales_order")
            vwrite(e)
            vwrite(parsed_order)
            if e.args and e.args[0]:
                raise e
            else:
                make_amazon_log(title=e.message, status="Error", method="create_sales_order",
                              message=frappe.get_traceback(),
                              request_data=parsed_order.get("order_details").get("order_id"), exception=True)
    else:
        so = frappe.get_doc("Sales Order", so)
    frappe.db.commit()
    return so

def get_variation_details(amazon_order_item):
    variation_details = ""
    attr_list = amazon_order_item.get("Variation").get("VariationSpecifics").get("NameValueList")
    for attr in attr_list:
        variation_details = variation_details + attr.get("Name") + ':' + attr.get("Value") + ' ; '
    return variation_details

def get_order_items(order_items, amazon_settings):
    items = []
    for amazon_item in order_items:
        # if('Variation' in amazon_item):
        if False: # yet to find parameter to find varaint items
            item_code = get_variant_item_code(amazon_item)
            if item_code == None:
                # check if item is mapped to non-variant item
                item_code = get_item_code(amazon_item)
                if item_code == None:
                    make_amazon_log(title="Variant Item not found", status="Error", method="get_order_items",
                              message="Variant Item not found for %s" %(amazon_item.get("Item").get("ItemID")),request_data=amazon_item.get("Item").get("ItemID"))
        else:
            item_code = get_item_code(amazon_item)
            if item_code == None:
                make_amazon_log(title="Item not found", status="Error", method="get_order_items",
                              message="Item not found for %s" %(amazon_item.get("Item").get("ItemID")),request_data=amazon_item.get("Item").get("ItemID"))
        items.append({
            "item_code": item_code,
            "item_name": amazon_item.Title[:140],
            "rate": float(amazon_item.ItemPrice)/float(amazon_item.QuantityOrdered) + float(amazon_item.ItemTax),
            "qty": amazon_item.QuantityOrdered,
            # "stock_uom": amazon_item.get("sku"),
            "warehouse": amazon_settings.warehouse
        })
    return items

def get_item_code(amazon_item):
    # item_code = frappe.db.get_value("Item", {"amazon_variant_id": amazon_item.get("variant_id")}, "item_code")
    item_code = False
    if not item_code:
        # item_code = frappe.db.get_value("Item", {"amazon_product_id": amazon_item.get("Item").get("ItemID")}, "item_code")
        item_id = amazon_item.ASIN
        item_code_query = """ select item_code from `tabItem` where amazon_product_id='%s' or amazon_product_id like '%s' or amazon_product_id like '%s' or amazon_product_id like '%s'""" % (item_id,item_id+",%","%,"+item_id+",%","%,"+item_id)
        item_code_result = frappe.db.sql(item_code_query, as_dict=1)
        if len(item_code_result)>1:
            # getting non-variant item - erpnext_amazon/issue#4
            filter_query = """ select item_code from `tabItem` where variant_of is null and (amazon_product_id='%s' or amazon_product_id like '%s' or amazon_product_id like '%s' or amazon_product_id like '%s')""" % (item_id,item_id+",%","%,"+item_id+",%","%,"+item_id)
            filter_result = frappe.db.sql(filter_query, as_dict=1)
            item_code = filter_result[0].get("item_code")
        else:
            if len(item_code_result):
                item_code = item_code_result[0].get("item_code")
    return item_code

def get_variant_item_code(amazon_item):
    # item = frappe.get_doc("Item", {"amazon_product_id": amazon_item.get("Item").get("ItemID")})
    # item_code = item.get("item_code")
    item_id = amazon_item.get("Item").get("ItemID")
    item_code_query = """ select item_code from `tabItem` where amazon_product_id='%s' or amazon_product_id like '%s' or amazon_product_id like '%s' or amazon_product_id like '%s'""" % (
    item_id, item_id+",%", "%,"+item_id+",%", "%,"+item_id)
    item_code_result = frappe.db.sql(item_code_query, as_dict=1)
    if len(item_code_result) > 1:
        # getting non-variant item - erpnext_amazon/issue#4
        filter_query = """ select item_code from `tabItem` where variant_of is null and (amazon_product_id='%s' or amazon_product_id like '%s' or amazon_product_id like '%s' or amazon_product_id like '%s')""" % (
        item_id, item_id + ",%", "%," + item_id + ",%", "%," + item_id)
        filter_result = frappe.db.sql(filter_query, as_dict=1)
        item_code = filter_result[0].get("item_code")
    else:
        item_code = item_code_result[0].get("item_code")
    variant_items_query = """ select item_code from `tabItem` where variant_of='%s'""" % (item_code)
    variant_items_result = frappe.db.sql(variant_items_query, as_dict=1)
    all_variation_specifics = amazon_item.get("Variation").get("VariationSpecifics").get("NameValueList")
    variation_specifics = []
    if (type(all_variation_specifics) is dict):
        if 'warranty' not in all_variation_specifics.get("Name").lower():
            variation_specifics.append(all_variation_specifics)
    else:
        for required_variation_specifics in all_variation_specifics:
            # if required_variation_specifics.get("Name").lower()!='warranty':
            if 'warranty' not in required_variation_specifics.get("Name").lower():
                variation_specifics.append(required_variation_specifics)
    for variant_item in variant_items_result:
        # get records from tabItemVariantAttributes where parent=variant_item
        variant_attributes_query = """ select * from `tabItem Variant Attribute` where parent='%s' and attribute != 'Warranty'""" % (variant_item.get("item_code"))
        variant_attributes_result = frappe.db.sql(variant_attributes_query, as_dict=1)
        # >> amazon may have extra attributes which we won't consider in erp, so removing equal length condition
        # if len(variant_attributes_result)==len(variation_specifics):
        #     # for each variation specific, compare with result row
        #     matched = 0
        #     for variation_specific in variation_specifics:
        #         for variant_attributes_row in variant_attributes_result:
        #             if((variant_attributes_row.get("attribute").lower()==variation_specific.get("Name").lower()) and (variant_attributes_row.get("attribute_value").lower()==variation_specific.get("Value").lower())):
        #                 matched = matched+1
        #             if len(variation_specifics)==matched:
        #                 return variant_item.get("item_code")
        matched = 0
        for variant_attributes_row in variant_attributes_result:
            for variation_specific in variation_specifics:
                if ((variant_attributes_row.get("attribute").lower() == variation_specific.get("Name").lower()) and (
                    variant_attributes_row.get("attribute_value").lower() == variation_specific.get("Value").lower())):
                    matched = matched + 1
        if len(variant_attributes_result) == matched:
            return variant_item.get("item_code")
            # << amazon may have extra attributes which we won't consider in erp, so removing equal length condition
    return None
