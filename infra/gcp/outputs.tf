output "project_id" {
  value = var.project_id
}

output "project_number" {
  value = var.project_number
}

output "region" {
  value = var.region
}

output "state_bucket" {
  value = google_storage_bucket.tfstate.name
}

output "data_bucket" {
  value = google_storage_bucket.data.name
}

output "migrator_service_account" {
  value = google_service_account.migrator.email
}

output "budget_name" {
  value = google_billing_budget.monthly.name
}
