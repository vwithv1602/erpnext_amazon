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
    response = None
    conn = MWSConnection(
    host=settings.host,
    aws_access_key_id=settings.access_key_id,
    aws_secret_access_key=settings.secret_access_key,
    Merchant=settings.merchant_id)
    if path == 'list_inventory_supply':
        try:
            response = conn.list_inventory_supply(SellerSkus=[params.get("SellerSkus")])
        except Exception as e:
            vwrite("Exception raised in get_request - get_product_categories_for_asin")
            vwrite(e)
            vwrite(e.message)
    if path == 'get_matching_product':
        try:
            response = conn.get_matching_product(MarketplaceId=settings.market_place_id,ASINList=[params.get("ASIN")])
        except Exception as e:
            vwrite("Exception raised in get_request - get_product_categories_for_asin")
            vwrite(e)
            vwrite(e.message)
    if path == 'list_orders':
        try:
            response = conn.list_orders(LastUpdatedAfter=lastSync,MarketplaceId=[settings.market_place_id])
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
    if path == 'submit_feed':
        try:
            feed = conn.submit_feed(
                FeedType = params.get("feed_type"),
                PurgeAndReplace = False,
                MarketplaceIdList = [settings.market_place_id],
                content_type = 'text/xml',
                FeedContent = params.get("feed_content")
            )
            response = feed.SubmitFeedResult.FeedSubmissionInfo
        except Exception as e:
            vwrite("Exception raised in get_request - submit_feed")
            vwrite(params)
            vwrite(e)
            vwrite(e.message)
    if path == 'get_feed_submission_list':
        try: 
            response = conn.get_feed_submission_list(
                FeedSubmissionIdList=[params.get('feed_submission_id')]
            )
        except Exception as e:
            vwrite("Exception raised in get_request - get_feed_submission_list")
            vwrite(params)
            vwrite(e)
            vwrite(e.message)
    if path == 'get_feed_submission_result':
        try:
            response = conn.get_feed_submission_result(FeedSubmissionId=params.get("id"))
        except Exception as e:
            vwrite("Exception raised in get_request - get_feed_submission_result")
            vwrite(params)
            vwrite(e)
            vwrite(e.message)
    if path == 'request_report':
        try:
            response = conn.request_report(ReportType=params.get("ReportType"))
        except Exception as e:
            vwrite("Exception raised in get_request - request_report")
            vwrite(params)
            vwrite(e)
            vwrite(e.message)
    if path == 'get_report_request_list':
        try:
            response = conn.get_report_request_list(ReportRequestIdList=params.get("ReportRequestIdList"))
        except Exception as e:
            vwrite("Exception raised in get_request - get_report_request_list")
            vwrite(params)
            vwrite(e)
            vwrite(e.message)
    if path == 'get_report':
        try:
            response = conn.get_report(ReportId=params.get("ReportId"))
        except Exception as e:
            vwrite("Exception raised in get_request - get_report")
            vwrite(params)
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
