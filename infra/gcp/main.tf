locals {
  labels = {
    application = "falando-nela"
    managed-by  = "opentofu"
    phase       = "g01"
  }
  required_services = toset([
    "billingbudgets.googleapis.com",
    "cloudbilling.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "storage.googleapis.com",
  ])
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "tfstate" {
  name                        = var.state_bucket
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = merge(local.labels, { purpose = "tfstate" })

  versioning {
    enabled = true
  }

  soft_delete_policy {
    retention_duration_seconds = 604800
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_storage_bucket" "data" {
  name                        = var.data_bucket
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = merge(local.labels, { purpose = "data" })

  versioning {
    enabled = false
  }

  soft_delete_policy {
    retention_duration_seconds = 604800
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_service_account" "migrator" {
  project      = var.project_id
  account_id   = "fn-migrator"
  display_name = "Falando Nela data migrator"
  description  = "Identidade sem chave para a migração imutável Drive para GCS."

  depends_on = [google_project_service.required["iam.googleapis.com"]]
}

resource "google_storage_bucket_iam_member" "migrator_creator" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.migrator.email}"
}

resource "google_storage_bucket_iam_member" "migrator_viewer" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.migrator.email}"
}

resource "google_service_account_iam_member" "operator_token_creator" {
  service_account_id = google_service_account.migrator.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = var.operator_principal

  depends_on = [google_project_service.required["iamcredentials.googleapis.com"]]
}

resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account_id
  display_name    = "falando-nela-gcp-first"

  budget_filter {
    projects = ["projects/${var.project_number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = "5"
    }
  }

  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.9
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = []
    disable_default_iam_recipients   = false
    enable_project_level_recipients  = true
  }

  depends_on = [google_project_service.required["billingbudgets.googleapis.com"]]
}
