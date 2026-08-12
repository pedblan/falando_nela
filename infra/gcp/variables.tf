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
