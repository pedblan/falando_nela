variable "project_id" {
  description = "Project ID explícito do Falando Nela."
  type        = string

  validation {
    condition     = var.project_id == "falando-nela-pedblan"
    error_message = "project_id deve coincidir com o contrato G01."
  }
}

variable "project_number" {
  description = "Project number explícito e versionado do Falando Nela."
  type        = string

  validation {
    condition     = var.project_number == "818569314985"
    error_message = "project_number deve coincidir com o contrato G01."
  }
}

variable "region" {
  description = "Região única inicial."
  type        = string

  validation {
    condition     = var.region == "southamerica-east1"
    error_message = "region deve coincidir com o contrato G01."
  }
}

variable "state_bucket" {
  description = "Bucket de state criado no bootstrap e importado."
  type        = string

  validation {
    condition     = var.state_bucket == "falando-nela-pedblan-tfstate"
    error_message = "state_bucket deve coincidir com o contrato G01."
  }
}

variable "data_bucket" {
  description = "Bucket privado dos dados."
  type        = string

  validation {
    condition     = var.data_bucket == "falando-nela-pedblan-data"
    error_message = "data_bucket deve coincidir com o contrato G01."
  }
}

variable "billing_account_id" {
  description = "Billing account obtida por readback e nunca versionada."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account_id))
    error_message = "billing_account_id deve usar o formato XXXXXX-XXXXXX-XXXXXX."
  }
}

variable "operator_principal" {
  description = "Principal user:... confirmado por readback e nunca versionado."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^user:[^[:space:]@]+@[^[:space:]@]+$", var.operator_principal))
    error_message = "operator_principal deve ser um member IAM user:... válido."
  }
}

variable "pipeline_image" {
  description = "Imagem G03 por digest; null prepara somente a fundação de build."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = var.pipeline_image == null || can(regex(
      "^southamerica-east1-docker[.]pkg[.]dev/falando-nela-pedblan/falando-nela/parquet-pilot@sha256:[0-9a-f]{64}$",
      var.pipeline_image,
    ))
    error_message = "pipeline_image deve ser a referência Artifact Registry G03 por digest."
  }
}

variable "pipeline_operation_id" {
  description = "Operation ID imutável da execução piloto G03."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.pipeline_operation_id == null ||
      can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$", var.pipeline_operation_id))
    )
    error_message = "pipeline_operation_id inválido."
  }
}

variable "pipeline_revision" {
  description = "Commit/revisão incorporado à imagem e ao manifesto G03."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.pipeline_revision == null ||
      can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$", var.pipeline_revision))
    )
    error_message = "pipeline_revision inválida."
  }
}

variable "marimo_image" {
  description = "Imagem OCI do app Marimo por digest."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.marimo_image == null ||
      can(regex(
        "^southamerica-east1-docker[.]pkg[.]dev/falando-nela-pedblan/falando-nela/marimo-primeiro@sha256:[0-9a-f]{64}$",
        var.marimo_image,
      ))
    )
    error_message = "marimo_image deve ser uma imagem registrada por digest no repositório local."
  }
}
