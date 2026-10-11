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

		frm.add_custom_button(__("Generate Summary"), () => generate_summary(frm, false));
		frm.add_custom_button(__("Force Regenerate"), () => {
			frappe.confirm(
				__("Call the LLM again even when the current summary inputs have not changed?"),
				() => generate_summary(frm, true),
			);
		});

		frm.add_custom_button(__("Summary"), () => copy_report(frm, false), __("Copy"));
		frm.add_custom_button(__("Summary + Timeline"), () => copy_report(frm, true), __("Copy"));
	},
});


function generate_summary(frm, force) {
	if (!frm.doc.report_date) {
		frappe.msgprint(__("Set Report Date before generating a summary."));
		return;
	}

	frappe.call({
		method: "kairos.api.generate_day_summary",
		args: { report_date: frm.doc.report_date, force },
		freeze: true,
		freeze_message: force ? __("Regenerating AI summary...") : __("Generating AI summary..."),
		callback: (response) => {
			if (response.exc) {
				return;
			}
			const result = response.message;
			const message = result.cache_hit
				? __("Summary reused because its inputs have not changed.")
				: result.generation_mode === "fallback"
					? __("AI unavailable; a fallback summary was generated.")
					: __("Summary generated successfully.");
			frappe.show_alert({ message, indicator: result.generation_mode === "fallback" ? "orange" : "green" });
			if (frm.doc.name === result.report_name) {
				frm.reload_doc();
			} else {
				frappe.set_route("Form", "Kairos Day Report", result.report_name);
			}
		},
	});
}


async function copy_report(frm, include_timeline) {
	const summary = (frm.doc.summary_text || "").trim();
	const timeline = (frm.doc.timeline_text || "").trim();

	if (!summary) {
		frappe.msgprint(__("Generate a summary before copying the report."));
		return;
	}

	const text = include_timeline && timeline ? `${summary}\n\n---\n\n${timeline}` : summary;
	try {
		await write_to_clipboard(text);
		frappe.show_alert({ message: __("Report copied to clipboard."), indicator: "green" });
	} catch (error) {
		console.error("Kairos copy failed", error);
		frappe.msgprint(__("Could not copy automatically. Check browser clipboard permissions and try again."));
	}
}


async function write_to_clipboard(text) {
	if (navigator.clipboard && window.isSecureContext) {
		await navigator.clipboard.writeText(text);
		return;
	}

	const textarea = document.createElement("textarea");
	textarea.value = text;
	textarea.setAttribute("readonly", "");
	textarea.style.position = "fixed";
	textarea.style.opacity = "0";
	document.body.appendChild(textarea);
	textarea.select();
	const copied = document.execCommand("copy");
	document.body.removeChild(textarea);
	if (!copied) {
		throw new Error("Browser copy command was rejected.");
	}
}
