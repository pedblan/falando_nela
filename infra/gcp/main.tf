locals {
  labels = {
    application = "falando-nela"
    managed-by  = "opentofu"
    phase       = "g01"
  }
  required_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudbilling.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
  ])
  g03_labels = {
    application = "falando-nela"
    managed-by  = "opentofu"
    phase       = "g03"
  }
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

resource "google_artifact_registry_repository" "pipeline" {
  project       = var.project_id
  location      = var.region
  repository_id = "falando-nela"
  description   = "Imagens OCI dos jobs do Falando Nela."
  format        = "DOCKER"
  mode          = "STANDARD_REPOSITORY"
  labels        = local.g03_labels

  docker_config {
    immutable_tags = true
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.required["artifactregistry.googleapis.com"]]
}

resource "google_service_account" "pipeline" {
  project      = var.project_id
  account_id   = "fn-pipeline"
  display_name = "Falando Nela Parquet pipeline"
  description  = "Identidade sem chave do Cloud Run Job G03."

  depends_on = [google_project_service.required["iam.googleapis.com"]]
}

resource "google_service_account" "builder" {
  project      = var.project_id
  account_id   = "fn-builder"
  display_name = "Falando Nela image builder"
  description  = "Identidade sem chave do build G03 no Cloud Build."

  depends_on = [google_project_service.required["iam.googleapis.com"]]
}

resource "google_artifact_registry_repository_iam_member" "builder_writer" {
  project    = var.project_id
  location   = google_artifact_registry_repository.pipeline.location
  repository = google_artifact_registry_repository.pipeline.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_project_iam_member" "builder_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_storage_bucket_iam_member" "builder_source_viewer" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.builder.email}"

  condition {
    title       = "g03-read-build-source"
    description = "Leitura somente do pacote-fonte enviado para o build G03."
    expression  = "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.data.name}/objects/operations/builds/g03/')"
  }
}

resource "google_service_account_iam_member" "operator_builder_user" {
  service_account_id = google_service_account.builder.name
  role               = "roles/iam.serviceAccountUser"
  member             = var.operator_principal
}

resource "google_service_account_iam_member" "cloud_build_builder_token_creator" {
  service_account_id = google_service_account.builder.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${var.project_number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"

  depends_on = [google_project_service.required["cloudbuild.googleapis.com"]]
}

resource "google_artifact_registry_repository_iam_member" "cloud_run_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.pipeline.location
  repository = google_artifact_registry_repository.pipeline.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:service-${var.project_number}@serverless-robot-prod.iam.gserviceaccount.com"

  depends_on = [google_project_service.required["run.googleapis.com"]]
}

resource "google_service_account_iam_member" "operator_pipeline_user" {
  service_account_id = google_service_account.pipeline.name
  role               = "roles/iam.serviceAccountUser"
  member             = var.operator_principal
}

resource "google_storage_bucket_iam_member" "pipeline_viewer" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.pipeline.email}"

  condition {
    title       = "g03-read-input-and-own-output"
    description = "Leitura do recorte raw 2010 e dos artefatos G03 para reconciliação."
    expression = join(" || ", [
      "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.data.name}/objects/data/raw/v1/senado/plenario_discursos/ano=2010/')",
      "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.data.name}/objects/data/processed/v1/g03/')",
      "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.data.name}/objects/manifests/processing/g03/')",
    ])
  }
}

resource "google_storage_bucket_iam_member" "pipeline_creator" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.pipeline.email}"

  condition {
    title       = "g03-create-own-output"
    description = "Criação sem overwrite dos Parquets e manifests G03."
    expression = join(" || ", [
      "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.data.name}/objects/data/processed/v1/g03/')",
      "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.data.name}/objects/manifests/processing/g03/')",
    ])
  }
}

resource "google_cloud_run_v2_job" "pipeline" {
  count = var.pipeline_image == null ? 0 : 1

  project             = var.project_id
  location            = var.region
  name                = "fn-parquet-pilot"
  deletion_protection = true
  launch_stage        = "GA"

  template {
    task_count  = 1
    parallelism = 1
    labels      = local.g03_labels

    template {
      service_account       = google_service_account.pipeline.email
      timeout               = "600s"
      max_retries           = 0
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

      containers {
        name  = "parquet-pilot"
        image = var.pipeline_image
        args = [
          "parquet-pilot",
          "--operation-id=${var.pipeline_operation_id}",
          "--implementation-revision=${var.pipeline_revision}",
          "--through=publish",
          "--backend=gcs",
          "--selection-manifest=/app/specs/refundacao_gcp_first/g03_parquet_cloud_run/selection.json",
          "--work-root=/tmp/falando-nela/operations",
          "--gcp-config=/app/config/gcp.toml",
          "--confirm-project-id=${var.project_id}",
          "--confirm-region=${var.region}",
          "--confirm-bucket=${var.data_bucket}",
          "--confirm-authoritative-raw=gcs",
          "--json",
        ]

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.required["run.googleapis.com"],
    google_artifact_registry_repository.pipeline,
    google_storage_bucket_iam_member.pipeline_creator,
    google_storage_bucket_iam_member.pipeline_viewer,
  ]
}

check "pipeline_job_inputs" {
  assert {
    condition = (
      (var.pipeline_image == null && var.pipeline_operation_id == null && var.pipeline_revision == null) ||
      (var.pipeline_image != null && var.pipeline_operation_id != null && var.pipeline_revision != null)
    )
    error_message = "pipeline_image, pipeline_operation_id e pipeline_revision devem ser informados juntos."
  }
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
      currency_code = "BRL"
      units         = "25"
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
