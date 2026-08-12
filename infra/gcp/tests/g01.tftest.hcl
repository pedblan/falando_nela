mock_provider "google" {}

override_resource {
  target = google_service_account.migrator
  values = {
    name  = "projects/falando-nela-pedblan/serviceAccounts/fn-migrator@falando-nela-pedblan.iam.gserviceaccount.com"
    email = "fn-migrator@falando-nela-pedblan.iam.gserviceaccount.com"
  }
}

override_resource {
  target = google_service_account.pipeline
  values = {
    name  = "projects/falando-nela-pedblan/serviceAccounts/fn-pipeline@falando-nela-pedblan.iam.gserviceaccount.com"
    email = "fn-pipeline@falando-nela-pedblan.iam.gserviceaccount.com"
  }
}

override_resource {
  target = google_service_account.builder
  values = {
    name  = "projects/falando-nela-pedblan/serviceAccounts/fn-builder@falando-nela-pedblan.iam.gserviceaccount.com"
    email = "fn-builder@falando-nela-pedblan.iam.gserviceaccount.com"
  }
}

run "g01_contract" {
  command = plan

  variables {
    project_id         = "falando-nela-pedblan"
    project_number     = "818569314985"
    region             = "southamerica-east1"
    state_bucket       = "falando-nela-pedblan-tfstate"
    data_bucket        = "falando-nela-pedblan-data"
    billing_account_id = "000000-000000-000000"
    operator_principal = "user:operador@example.invalid"
  }

  assert {
    condition     = google_storage_bucket.tfstate.location == "southamerica-east1"
    error_message = "state deve permanecer em São Paulo"
  }

  assert {
    condition     = google_storage_bucket.tfstate.versioning[0].enabled
    error_message = "state deve manter versionamento"
  }

  assert {
    condition = (
      google_storage_bucket.tfstate.soft_delete_policy[0].retention_duration_seconds == 604800 &&
      !google_storage_bucket.tfstate.force_destroy &&
      google_storage_bucket.tfstate.public_access_prevention == "enforced" &&
      google_storage_bucket.tfstate.uniform_bucket_level_access
    )
    error_message = "state deve manter todas as proteções G01"
  }

  assert {
    condition = (
      google_storage_bucket.data.public_access_prevention == "enforced" &&
      google_storage_bucket.data.uniform_bucket_level_access &&
      google_storage_bucket.data.soft_delete_policy[0].retention_duration_seconds == 604800 &&
      !google_storage_bucket.data.versioning[0].enabled &&
      !google_storage_bucket.data.force_destroy
    )
    error_message = "bucket de dados deve manter todas as proteções G01"
  }

  assert {
    condition = toset(keys(google_project_service.required)) == toset([
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
    error_message = "G03 deve preservar G01 e acrescentar somente as três APIs aprovadas"
  }

  assert {
    condition     = google_storage_bucket_iam_member.migrator_creator.role == "roles/storage.objectCreator"
    error_message = "migrator deve criar objetos sem administrar o bucket"
  }

  assert {
    condition     = google_storage_bucket_iam_member.migrator_viewer.role == "roles/storage.objectViewer"
    error_message = "migrator deve verificar os objetos copiados"
  }

  assert {
    condition     = google_service_account_iam_member.operator_token_creator.role == "roles/iam.serviceAccountTokenCreator"
    error_message = "operador deve somente impersonar a conta migradora"
  }

  assert {
    condition = (
      google_billing_budget.monthly.amount[0].specified_amount[0].currency_code == "BRL" &&
      google_billing_budget.monthly.amount[0].specified_amount[0].units == "25"
    )
    error_message = "budget mensal deve permanecer em R$ 25"
  }

  assert {
    condition = (
      !google_billing_budget.monthly.all_updates_rule[0].disable_default_iam_recipients &&
      google_billing_budget.monthly.all_updates_rule[0].enable_project_level_recipients
    )
    error_message = "budget deve notificar os destinatários IAM aprovados"
  }

  assert {
    condition     = google_billing_budget.monthly.budget_filter[0].projects == toset(["projects/818569314985"])
    error_message = "budget deve cobrir somente o projeto G01 explícito"
  }
}

run "g03_contract" {
  command = plan

  variables {
    project_id            = "falando-nela-pedblan"
    project_number        = "818569314985"
    region                = "southamerica-east1"
    state_bucket          = "falando-nela-pedblan-tfstate"
    data_bucket           = "falando-nela-pedblan-data"
    billing_account_id    = "000000-000000-000000"
    operator_principal    = "user:operador@example.invalid"
    pipeline_image        = "southamerica-east1-docker.pkg.dev/falando-nela-pedblan/falando-nela/parquet-pilot@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    pipeline_operation_id = "g03-pilot-test"
    pipeline_revision     = "abcdef1"
  }

  assert {
    condition = (
      google_artifact_registry_repository.pipeline.location == "southamerica-east1" &&
      google_artifact_registry_repository.pipeline.format == "DOCKER" &&
      google_artifact_registry_repository.pipeline.docker_config[0].immutable_tags
    )
    error_message = "Artifact Registry G03 deve ser regional, Docker e imutável"
  }

  assert {
    condition = (
      google_artifact_registry_repository_iam_member.builder_writer.role == "roles/artifactregistry.writer" &&
      google_project_iam_member.builder_log_writer.role == "roles/logging.logWriter" &&
      google_storage_bucket_iam_member.builder_source_viewer.role == "roles/storage.objectViewer" &&
      strcontains(
        google_storage_bucket_iam_member.builder_source_viewer.condition[0].expression,
        "/objects/operations/builds/g03/",
      ) &&
      google_service_account_iam_member.cloud_build_builder_token_creator.role == "roles/iam.serviceAccountTokenCreator" &&
      google_artifact_registry_repository_iam_member.cloud_run_reader.role == "roles/artifactregistry.reader"
    )
    error_message = "builder e Cloud Run devem manter somente os acessos mínimos previstos"
  }

  assert {
    condition = (
      google_storage_bucket_iam_member.pipeline_viewer.role == "roles/storage.objectViewer" &&
      google_storage_bucket_iam_member.pipeline_creator.role == "roles/storage.objectCreator"
    )
    error_message = "pipeline deve apenas ler e criar nos prefixos condicionados"
  }

  assert {
    condition = (
      google_cloud_run_v2_job.pipeline[0].location == "southamerica-east1" &&
      google_cloud_run_v2_job.pipeline[0].template[0].task_count == 1 &&
      google_cloud_run_v2_job.pipeline[0].template[0].parallelism == 1 &&
      google_cloud_run_v2_job.pipeline[0].template[0].template[0].max_retries == 0 &&
      google_cloud_run_v2_job.pipeline[0].template[0].template[0].timeout == "600s"
    )
    error_message = "job G03 deve manter uma tarefa, uma tentativa e timeout explícito"
  }

  assert {
    condition = (
      google_cloud_run_v2_job.pipeline[0].template[0].template[0].containers[0].resources[0].limits["cpu"] == "1" &&
      google_cloud_run_v2_job.pipeline[0].template[0].template[0].containers[0].resources[0].limits["memory"] == "1Gi" &&
      contains(google_cloud_run_v2_job.pipeline[0].template[0].template[0].containers[0].args, "--confirm-authoritative-raw=gcs")
    )
    error_message = "container G03 deve fixar recursos e autoridade GCS"
  }
}
