// Copyright (c) 2018, vavcoders and contributors
// For license information, please see license.txt

frappe.ui.form.on('Amazon Settings', {
	refresh: function(frm) {
		if(!frm.doc.__islocal && frm.doc.enable_amazon === 1){
            frm.add_custom_button(__('Sync Amazon'), function() {
                frappe.call({
                    method:"erpnext_amazon.api.sync_amazon",
                })
            }).addClass("btn-primary");
        }
        frm.add_custom_button(__("Amazon Log"), function(){
            frappe.set_route("List", "Amazon Log");
        })
        frm.add_custom_button(__('Sync Amazon Age'), function() {
            frappe.call({
                method:"erpnext_amazon.client.update_item_list_amazon_qty",
            })
        }).addClass("btn-primary");
	}
});
