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

output "pipeline_service_account" {
  value = google_service_account.pipeline.email
}

output "builder_service_account" {
  value = google_service_account.builder.email
}

output "marimo_service_account" {
  value = google_service_account.marimo.email
}

output "artifact_repository" {
  value = google_artifact_registry_repository.pipeline.name
}

output "pipeline_job" {
  value = try(google_cloud_run_v2_job.pipeline[0].name, null)
}

output "marimo_service" {
  value = try(google_cloud_run_v2_service.marimo[0].name, null)
}

output "marimo_service_url" {
  value = try(google_cloud_run_v2_service.marimo[0].uri, null)
}

output "budget_name" {
  value = google_billing_budget.monthly.name
}
