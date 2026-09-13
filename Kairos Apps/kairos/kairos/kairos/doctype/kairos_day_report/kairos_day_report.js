frappe.ui.form.on("Kairos Day Report", {
	refresh(frm) {
		frm.add_custom_button(__("Generate Timeline"), () => {
			if (!frm.doc.report_date) {
				frappe.msgprint(__("Set Report Date before generating a timeline."));
				return;
			}

			frappe.call({
				method: "kairos.api.generate_day_timeline",
				args: { report_date: frm.doc.report_date },
				freeze: true,
				freeze_message: __("Generating timeline..."),
				callback: (response) => {
					if (!response.exc) {
						frappe.set_route("Form", "Kairos Day Report", response.message.report_name);
					}
				},
			});
		});

		frm.add_custom_button(__("Generate Summary"), () => {
			if (!frm.doc.report_date) {
				frappe.msgprint(__("Set Report Date before generating a summary."));
				return;
			}

			frappe.call({
				method: "kairos.api.generate_day_summary",
				args: { report_date: frm.doc.report_date },
				freeze: true,
				freeze_message: __("Generating AI summary..."),
				callback: (response) => {
					if (!response.exc) {
						frappe.set_route("Form", "Kairos Day Report", response.message.report_name);
					}
				},
			});
		});
	},
});
