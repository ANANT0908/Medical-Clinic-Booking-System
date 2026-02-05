terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = "4.51.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = "us-central1"
}

variable "project_id" {
  description = "The ID of the Google Cloud project"
  type        = string
}

# Cloud SQL
resource "google_sql_database_instance" "db" {
  name             = "medical-booking-db"
  database_version = "POSTGRES_14"
  region           = "us-central1"
  
  settings {
    tier = "db-f1-micro"
  }
  deletion_protection  = false 
}

resource "google_sql_database" "database" {
  name     = "medical_booking_db"
  instance = google_sql_database_instance.db.name
}

resource "google_sql_user" "users" {
  name     = "postgres"
  instance = google_sql_database_instance.db.name
  password = "postgres" # In prod, use secret manager
}

# Pub/Sub
resource "google_pubsub_topic" "events" {
  name = "booking-events"
}

# Subscriptions (Push to Cloud Run)
# Note: In a real deployment, we need the Cloud Run URL to set up the push config.
# Circular dependency issue: Cloud Run needs Pub/Sub topic env var, Pub/Sub needs Cloud Run URL.
# Setup: 
# 1. Deploy Cloud Run with dummy topic variable or allow it to be updated later.
# 2. Create Pub/Sub topic.
# 3. Create Subscription with Push Endpoint.
# Terraform handles this if we reference the cloud run service attribute.

# Validation Service Subscription
resource "google_pubsub_subscription" "validation" {
  name  = "validation-sub"
  topic = google_pubsub_topic.events.name
  filter = "attributes.event_type = \"booking.initiated\""
  
  push_config {
    push_endpoint = google_cloud_run_service.validation_service.status[0].url
    
    # OIDC Token needed for authenticated push
    # oidc_token {
    #   service_account_email = google_service_account.pubsub_invoker.email
    # }
  }
}

# Pricing Service Subscription
resource "google_pubsub_subscription" "pricing" {
  name  = "pricing-sub"
  topic = google_pubsub_topic.events.name
  filter = "attributes.event_type = \"booking.validated\""
  
  push_config {
    push_endpoint = google_cloud_run_service.pricing_service.status[0].url
  }
}

# Quota Manager Service Subscription
resource "google_pubsub_subscription" "quota" {
  name  = "quota-sub"
  topic = google_pubsub_topic.events.name
  filter = "attributes.event_type = \"booking.priced\" OR attributes.event_type = \"booking.compensate\""
  
  push_config {
    push_endpoint = google_cloud_run_service.quota_manager.status[0].url
  }
}

# Orchestrator Subscription (Wildcard)
resource "google_pubsub_subscription" "orchestrator" {
  name  = "orchestrator-sub"
  topic = google_pubsub_topic.events.name
  # Orchestrator listens to everything to update state
  
  push_config {
    push_endpoint = google_cloud_run_service.orchestrator.status[0].url
  }
}

# Cloud Run Services

resource "google_cloud_run_service" "api_gateway" {
  name     = "api-gateway"
  location = "us-central1"
  
  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/api-gateway:latest"
        env {
            name = "PROJECT_ID"
            value = var.project_id
        }
        env {
            name = "TOPIC_ID"
            value = google_pubsub_topic.events.name
        }
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}

resource "google_cloud_run_service" "validation_service" {
  name     = "validation-service"
  location = "us-central1"
  
  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/validation-service:latest"
        env {
            name = "PROJECT_ID"
            value = var.project_id
        }
        env {
            name = "TOPIC_ID"
            value = google_pubsub_topic.events.name
        }
      }
    }
  }
}

resource "google_cloud_run_service" "pricing_service" {
  name     = "pricing-service"
  location = "us-central1"
  
  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/pricing-service:latest"
        env {
            name = "PROJECT_ID"
            value = var.project_id
        }
        env {
            name = "TOPIC_ID"
            value = google_pubsub_topic.events.name
        }
      }
    }
  }
}

resource "google_cloud_run_service" "quota_manager" {
  name     = "quota-manager"
  location = "us-central1"
  
  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/quota-manager:latest"
        env {
            name = "PROJECT_ID"
            value = var.project_id
        }
        env {
            name = "TOPIC_ID"
            value = google_pubsub_topic.events.name
        }
        # In real world, add DB connection env vars here
        # env { name = "DATABASE_URL"; value = ... }
      }
    }
  }
}

resource "google_cloud_run_service" "orchestrator" {
  name     = "orchestrator"
  location = "us-central1"
  
  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/booking-orchestrator:latest"
         env {
            name = "PROJECT_ID"
            value = var.project_id
        }
        env {
            name = "TOPIC_ID"
            value = google_pubsub_topic.events.name
        }
        # In real world, add DB connection env vars here
      }
    }
  }
}

# Outputs
output "api_gateway_url" {
  value = google_cloud_run_service.api_gateway.status[0].url
}
