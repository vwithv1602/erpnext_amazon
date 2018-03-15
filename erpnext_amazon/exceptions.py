from __future__ import unicode_literals
import frappe

class AmazonError(frappe.ValidationError): pass
class AmazonSetupError(frappe.ValidationError): pass