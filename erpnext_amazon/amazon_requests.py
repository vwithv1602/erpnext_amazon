import frappe
from frappe import _
from datetime import datetime,timedelta
from .exceptions import AmazonError
from boto.mws.connection import MWSConnection
from .vlog import vwrite


def get_request(path,params):
    settings = get_amazon_settings()
    lastSyncString = settings.last_sync_datetime
    lastSyncString = lastSyncString[:19]
    lastSyncObj = datetime.strptime(lastSyncString, '%Y-%m-%d %H:%M:%S')
    lastSync = (lastSyncObj + timedelta(-1)).isoformat()
    orders_response = None
    conn = MWSConnection(
    host=settings.host,
    aws_access_key_id=settings.access_key_id,
    aws_secret_access_key=settings.secret_access_key,
    Merchant=settings.merchant_id)
    if path == 'list_orders':
        try:
            response = conn.list_orders(CreatedAfter=lastSync,MarketplaceId=[settings.market_place_id])
        except Exception as e:
            vwrite("Exception raised in get_request - list_orders")
            vwrite(e)
            vwrite(e.message)
    if path == 'list_order_items':
        try:
            response = conn.list_order_items(CreatedAfter=lastSync,MarketplaceId=[settings.market_place_id],AmazonOrderId=params.get("AmazonOrderId"))
        except Exception as e:
            vwrite("Exception raised in get_request - list_order_items")
            vwrite(e)
            vwrite(e.message)
    return response

def get_amazon_settings():
    d = frappe.get_doc("Amazon Settings")

    if d.access_key_id:
        # if d.app_type == "Private" and d.password:
        #     d.password = d.get_password()
        return d.as_dict()
    else:
        frappe.throw(_("Amazon store Access Key Id is not configured on Amazon Settings"), AmazonError)