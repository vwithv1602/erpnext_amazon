from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
# from .amazon_requests import post_request, get_request
from .utils import make_amazon_log
from vlog import vwrite

# def sync_customers():
# 	amazon_customer_list = []
# 	sync_amazon_customers(amazon_customer_list)
# 	frappe.local.form_dict.count_dict["customers"] = len(amazon_customer_list)
#
# 	sync_erpnext_customers(amazon_customer_list)
#
# def sync_amazon_customers(amazon_customer_list):
# 	for amazon_customer in get_amazon_customers():
# 		if not frappe.db.get_value("Customer", {"amazon_customer_id": amazon_customer.get('id')}, "name"):
# 			create_customer(amazon_customer, amazon_customer_list)

def create_customer(parsed_order, amazon_customer_list):
	cust_id = parsed_order.get("customer_details").get("buyer_id")
	cust_name = parsed_order.get("customer_details").get("buyer_name")
	try:
		customer = frappe.get_doc({
			"doctype": "Customer",
			"name": cust_id,
			"customer_name" : cust_name,
			"amazon_customer_id": cust_id,
			# "sync_with_amazon": 1,
			# "customer_group": amazon_settings.customer_group,
			# "territory": frappe.utils.nestedset.get_root_of("Territory"),
			"customer_type": _("Individual")
		})
		customer.flags.ignore_mandatory = True
		customer.insert()
		if customer:
			create_customer_address(parsed_order, cust_id)
			create_customer_contact(parsed_order, cust_id)
		amazon_customer_list.append(parsed_order.get("customer_details").get("buyer_id"))
		frappe.db.commit()

			
	except Exception, e:
		vwrite("Exception raised in create_customer")
		vwrite(e.message)
		vwrite(parsed_order)
		if e.args[0] and e.args[0].startswith("402"):
			raise e
		else:
			make_amazon_log(title=e.message, status="Error", method="create_customer", message=frappe.get_traceback(),
				request_data=parsed_order.get("BuyerUserID"), exception=True)
		
def create_customer_address(parsed_order, amazon_customer):
	if not parsed_order.get("customer_details").get("buyer_name"):
		make_amazon_log(title=parsed_order.get("customer_details").get("buyer_email"), status="Error", method="create_customer_address", message="No shipping address found for %s" % parsed_order.get("customer_details").get("email"),
					  request_data=parsed_order.get("customer_details").get("buyer_email"), exception=True)
	else:
		try:
			if parsed_order.get("customer_details").get("buyer_address_line1"):
				address_line1 = parsed_order.get("customer_details").get("buyer_address_line1").replace("'", "")
			else:
				address_line1 = 'NA'
			if parsed_order.get("customer_details").get("buyer_address_line2"):
				address_line2 = parsed_order.get("customer_details").get("buyer_address_line2").replace("'", "")
			else:
				address_line2 = 'NA'
			if not frappe.db.get_value("Address",
									   {"amazon_address_id": parsed_order.get("customer_details").get("buyer_email")}, "name"):
				frappe.get_doc({
					"doctype": "Address",
					"amazon_address_id": parsed_order.get("customer_details").get("buyer_email"),
					"address_title": parsed_order.get("customer_details").get("buyer_name"),
					"address_type": "Shipping",
					"address_line1": address_line1,
					"address_line2": address_line2,
					"city": parsed_order.get("customer_details").get("buyer_city"),
					"state": parsed_order.get("customer_details").get("buyer_state"),
					"pincode": parsed_order.get("customer_details").get("buyer_zipcode"),
					# "country": amazon_order.get("ShippingAddress").get("Country"),
					"country": None,
					"phone": parsed_order.get("customer_details").get("buyer_phone"),
					"email_id": parsed_order.get("customer_details").get("buyer_email"),
					"links": [{
						"link_doctype": "Customer",
						# "link_name": amazon_order.get("BuyerUserID")
						"link_name": parsed_order.get("customer_details").get("buyer_name")
					}]
				}).insert()
			else:
				frappe.db.sql(
					"""update tabAddress set address_title='%s',address_type='Shipping',address_line1='%s',address_line2='%s',city='%s',state='%s',pincode='%s',country='%s',phone='%s',email_id='%s' where amazon_address_id='%s' """
					% (parsed_order.get("customer_details").get("buyer_name"), parsed_order.get("customer_details").get("buyer_address_line1"),
					   parsed_order.get("customer_details").get("buyer_address_line2"),
					   parsed_order.get("customer_details").get("buyer_city"),
					   parsed_order.get("customer_details").get("buyer_state"), parsed_order.get("customer_details").get("buyer_zipcode"),
					   "India",
					   parsed_order.get("customer_details").get("buyer_phone"),
					   parsed_order.get("customer_details").get("buyer_email"),
					   parsed_order.get("customer_details").get("buyer_email")))
				frappe.db.commit()

		except Exception, e:
			vwrite('Exception raised in create_customer_address')
			vwrite(e.message)
			vwrite(parsed_order)
			make_amazon_log(title=e.message, status="Error", method="create_customer_address",
						  message=frappe.get_traceback(),
						  request_data=amazon_customer, exception=True)


# create_customer_contact() will create customer contact in tabContact which is used in sending email
# to customer after creation of sales order. Stores firstname,lastname,emailID in tabContact
def create_customer_contact(parsed_order, amazon_customer):
	cust_name = parsed_order.get("customer_details").get("buyer_name")
	email_id = parsed_order.get("customer_details").get("buyer_email")
	if not cust_name:
		make_amazon_log(title=email_id, status="Error", method="create_customer_contact", message="Contact not found for %s" % email_id,
					  request_data=email_id, exception=True)
	else:
		try :
			if not frappe.db.get_value("Contact", {"first_name": amazon_customer}, "name"):
				frappe.get_doc({
					"doctype": "Contact",
					"first_name": amazon_customer,
					"email_id": email_id,
					"links": [{
						"link_doctype": "Customer",
						# "link_name": amazon_order.get("BuyerUserID")
						"link_name": cust_name
					}]
				}).insert()
			# else:
			# 	frappe.get_doc({
			# 		"doctype": "Contact",
			# 		"first_name": amazon_customer,
			# 		"email_id": email_id,
			# 		"links": [{
			# 			"link_doctype": "Customer",
			# 			# "link_name": amazon_order.get("BuyerUserID")
			# 			"link_name": amazon_order.get("ShippingAddress").get("Name")
			# 		}]
			# 	}).save()
		except Exception, e:
			vwrite("Exception raised in create_customer_contact")
			vwrite(e.message)
			vwrite(parsed_order)
			make_amazon_log(title=e.message, status="Error", method="create_customer_contact", message=frappe.get_traceback(),
				request_data=email_id, exception=True)

def get_address_title_and_type(customer_name, index):
	address_type = _("Billing")
	address_title = customer_name
	if frappe.db.get_value("Address", "{0}-{1}".format(customer_name.strip(), address_type)):
		address_title = "{0}-{1}".format(customer_name.strip(), index)
		
	return address_title, address_type 
	
def sync_erpnext_customers(amazon_customer_list):
	amazon_settings = frappe.get_doc("Amazon Settings", "Amazon Settings")
	
	condition = ["sync_with_amazon = 1"]
	
	last_sync_condition = ""
	if amazon_settings.last_sync_datetime:
		last_sync_condition = "modified >= '{0}' ".format(amazon_settings.last_sync_datetime)
		condition.append(last_sync_condition)
	
	customer_query = """select name, customer_name, amazon_customer_id from tabCustomer 
		where {0}""".format(" and ".join(condition))
		
	for customer in frappe.db.sql(customer_query, as_dict=1):
		try:
			if not customer.amazon_customer_id:
				create_customer_to_amazon(customer)
			
			else:
				if customer.amazon_customer_id not in amazon_customer_list:
					update_customer_to_amazon(customer, amazon_settings.last_sync_datetime)
			
			frappe.local.form_dict.count_dict["customers"] += 1
			frappe.db.commit()
		except Exception, e:
			make_amazon_log(title=e.message, status="Error", method="sync_erpnext_customers", message=frappe.get_traceback(),
				request_data=customer, exception=True)

def create_customer_to_amazon(customer):
	amazon_customer = {
		"first_name": customer['customer_name'],
	}
	
	amazon_customer = post_request("/admin/customers.json", { "customer": amazon_customer})
	
	customer = frappe.get_doc("Customer", customer['name'])
	customer.amazon_customer_id = amazon_customer['customer'].get("id")
	
	customer.flags.ignore_mandatory = True
	customer.save()
	
	addresses = get_customer_addresses(customer.as_dict())
	for address in addresses:
		sync_customer_address(customer, address)

def sync_customer_address(customer, address):
	address_name = address.pop("name")

	amazon_address = post_request("/admin/customers/{0}/addresses.json".format(customer.amazon_customer_id),
	{"address": address})
		
	address = frappe.get_doc("Address", address_name)
	address.amazon_address_id = amazon_address['customer_address'].get("id")
	address.save()
	
def update_customer_to_amazon(customer, last_sync_datetime):
	amazon_customer = {
		"first_name": customer['customer_name'],
		"last_name": ""
	}
	
	try:
		put_request("/admin/customers/{0}.json".format(customer.amazon_customer_id),\
			{ "customer": amazon_customer})
		update_address_details(customer, last_sync_datetime)
		
	except requests.exceptions.HTTPError, e:
		if e.args[0] and e.args[0].startswith("404"):
			customer = frappe.get_doc("Customer", customer.name)
			customer.amazon_customer_id = ""
			customer.sync_with_amazon = 0
			customer.flags.ignore_mandatory = True
			customer.save()
		else:
			raise
			
def update_address_details(customer, last_sync_datetime):
	customer_addresses = get_customer_addresses(customer, last_sync_datetime)
	for address in customer_addresses:
		if address.amazon_address_id:
			url = "/admin/customers/{0}/addresses/{1}.json".format(customer.amazon_customer_id,\
			address.amazon_address_id)
			
			address["id"] = address["amazon_address_id"]
			
			del address["amazon_address_id"]
			
			put_request(url, { "address": address})
			
		else:
			sync_customer_address(customer, address)
			
def get_customer_addresses(customer, last_sync_datetime=None):
	conditions = ["dl.parent = addr.name", "dl.link_doctype = 'Customer'",
		"dl.link_name = '{0}'".format(customer['name'])]
	
	if last_sync_datetime:
		last_sync_condition = "addr.modified >= '{0}'".format(last_sync_datetime)
		conditions.append(last_sync_condition)
	
	address_query = """select addr.name, addr.address_line1 as address1, addr.address_line2 as address2,
		addr.city as city, addr.state as province, addr.country as country, addr.pincode as zip,
		addr.amazon_address_id from tabAddress addr, `tabDynamic Link` dl
		where {0}""".format(' and '.join(conditions))
			
	return frappe.db.sql(address_query, as_dict=1)
