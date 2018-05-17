from __future__ import unicode_literals
import frappe
from frappe import _
from .sync_orders import sync_orders,sync_amazon_qty
from .utils import disable_amazon_sync_on_exception, make_amazon_log
from frappe.utils.background_jobs import enqueue
from datetime import datetime,timedelta
from .vlog import vwrite

@frappe.whitelist()
def sync_amazon():
    enqueue("erpnext_amazon.api.sync_amazon_resources", queue='long')
    frappe.msgprint(_("Queued for syncing. It may take a few minutes to an hour if this is your first sync."))

@frappe.whitelist()
def sync_amazon_resources():
    "Enqueue longjob for syncing amazon"
    amazon_settings = frappe.get_doc("Amazon Settings")
    make_amazon_log(title="Amazon Sync Job Queued", status="Queued", method=frappe.local.form_dict.cmd,
                     message="Amazon Sync Job Queued")
    if(amazon_settings.enable_amazon):
        try:
            now_time = frappe.utils.now()
            validate_amazon_settings(amazon_settings)
            frappe.local.form_dict.count_dict = {}
            # sync_products(amazon_settings.price_list, amazon_settings.warehouse)
            sync_orders()
            vwrite(" >> sync_amazon_qty")
            # sync_amazon_qty()
            vwrite(" << sync_amazon_qty")
            frappe.db.set_value("Amazon Settings", None, "last_sync_datetime", now_time)

            make_amazon_log(title="Sync Completed", status="Success", method=frappe.local.form_dict.cmd,
                             message="Amazon sync successfully completed")
        except Exception, e:
            if e.args[0] and hasattr(e.args[0], "startswith") and e.args[0].startswith("402"):
                make_amazon_log(title="Amazon has suspended your account", status="Error",
                                 method="sync_amazon_resources", message=_("""Amazon has suspended your account till
            		you complete the payment. We have disabled ERPNext Amazon Sync. Please enable it once
            		your complete the payment at Amazon."""), exception=True)

                disable_amazon_sync_on_exception()

            else:
                make_amazon_log(title="sync has terminated", status="Error", method="sync_amazon_resources",
                                 message=frappe.get_traceback(), exception=True)
    elif frappe.local.form_dict.cmd == "erpnext_amazon.api.sync_amazon":
        make_amazon_log(
            title="Amazon connector is disabled",
            status="Error",
            method="sync_amazon_resources",
            message=_(
                """Amazon connector is not enabled. Click on 'Connect to Amazon' to connect ERPNext and your Amazon store."""),
            exception=True)

def validate_amazon_settings(amazon_settings):
	"""
		This will validate mandatory fields and access token or app credentials
		by calling validate() of amazon settings.
	"""
	try:
		amazon_settings.save()
	except Exception, e:
		disable_amazon_sync_on_exception()
