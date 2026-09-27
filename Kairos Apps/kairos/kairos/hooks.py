app_name = "kairos"
app_title = "Kairos"
app_publisher = "Kairos"
app_description = "AI Work Assistant"
app_email = "cuongtoi124@gmail.com"
app_license = "mit"

# required_apps = []

# DocTypes / API / scheduler added in later A* / C* phases.

after_install = "kairos.install.after_install"
after_migrate = "kairos.install.after_migrate"

# Bench server time must be Asia/Ho_Chi_Minh; the job itself derives report_date in that timezone.
scheduler_events = {
	"cron": {
		"30 18 * * *": ["kairos.scheduler.generate_daily_draft"],
	},
}
