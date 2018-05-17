from __future__ import unicode_literals
from datetime import datetime,timedelta
import frappe
from frappe import _
from .exceptions import AmazonError
from .utils import make_amazon_log
import frappe
from frappe.utils import flt, nowdate, cint
from .amazon_requests import get_request,get_amazon_settings
from vlog import vwrite
from boto.mws import connection
import time
from jinja2 import Environment, PackageLoader

class UpdateQtyMessage(object):
    def __init__(self, sku, quantity, fulfillmentlatency):
        self.SKU = sku
        self.Quantity = quantity
        self.FulfillmentLatency = fulfillmentlatency
def get_sku_of_item(amazon_product_id):
    sku = None
    try:
        sku = frappe.db.get_value("Item", {"amazon_product_id": amazon_product_id}, "amazon_sku")
    except Exception, e:
        vwrite("Exception raised in get_sku_of_item")
        vwrite(e)
        vwrite(e.message)
    return sku
def update_qty_in_amazon_site(update_data):
    # submission_list = get_request('get_feed_submission_list',{'feed_submission_id':'50111017665'})
    # feedResult = get_request('get_feed_submission_result',{'id':'50111017665'})
    # vwrite(feedResult)
    # return False
    # vwrite("Update %s(%s) with qty: %s" %(amazon_product_id,item_code,qty_to_be_updated))
    # Update qty for items which are Fulfilled by Seller only. Do not update for Fulfilled by Amazon
    # vwrite("in update_qty_in_amazon_site:: amazon_product_id: %s, qty_to_be_updated: %s" %(amazon_product_id,qty_to_be_updated))
    settings = get_amazon_settings()
    MarketPlaceID = settings.market_place_id
    MerchantID = settings.merchant_id
    AccessKeyID = settings.access_key_id
    SecretKey = settings.secret_access_key
    env = Environment(loader=PackageLoader('erpnext_amazon', 'templates'),
                  trim_blocks=True,
                  lstrip_blocks=True)
    template = env.get_template('update_quantity_available.xml')
    feed_messages = []
    for data in update_data:
        # data['sku'] = "TEST"
        data['sku'] = get_sku_of_item(data.get("amazon_product_id"))
        if data.get('sku'):
            feed_messages.append(UpdateQtyMessage(data.get('sku'),data.get('qty_to_be_updated'),1))

    namespace = dict(MerchantId=MerchantID, FeedMessages=feed_messages)
    feed_content = template.render(namespace).encode('utf-8')
    params = {
        'feed_type': '_POST_INVENTORY_AVAILABILITY_DATA_',
        'feed_content': feed_content
    }
    vwrite("sending feed_content: %s" % datetime.now().isoformat())
    vwrite(feed_content)
    if len(feed_messages)>0:
        feed_info = get_request('submit_feed',params)
        vwrite("output after service call")
        vwrite(str(feed_info))
        # for checking feed status
        while True:
            submission_list = get_request('get_feed_submission_list',{'feed_submission_id':feed_info.FeedSubmissionId})
            info =  submission_list.GetFeedSubmissionListResult.FeedSubmissionInfo[0]
            id = info.FeedSubmissionId
            status = info.FeedProcessingStatus
            vwrite('Submission Id: {}. Current status: {}'.format(id, status))

            if (status in ('_SUBMITTED_', '_IN_PROGRESS_', '_UNCONFIRMED_')):
                vwrite('Sleeping and check again....')
                time.sleep(60)
            elif (status == '_DONE_'):
                feedResult = get_request('get_feed_submission_result',{'id':id})
                vwrite(feedResult)
                break
            else:
                vwrite("Submission processing error. Quit.")
                break