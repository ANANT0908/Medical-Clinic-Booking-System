# Medical Clinic Booking System

A production-ready event-driven medical booking system with SAGA Choreography.

## Architecture

- **API Gateway**: HTTP Entry point.
- **Validation**: Validates business rules.
- **Pricing**: Calculates dynamic pricing (Birthday/Female discounts).
- **Quota Manager**: Manages daily discount limits using DB locking.
- **Orchestrator**: Coordinates the SAGA transaction and compensation.

## Project Structure

```
/
├── services/               # Microservices
│   ├── api-gateway/
│   ├── validation-service/
│   ├── pricing-service/
│   ├── quota-manager/
│   └── booking-orchestrator/
├── database/               # SQL Schemas and Functions
├── infrastructure/         # Terraform for GCP
└── cli-client/             # Python CLI for interaction
```

## Quick Start (Deploy to GCP)

1.  **Prerequisites**: GCP Project, gcloud CLI, Terraform.
2.  **Infrastructure**:
    ```bash
    cd infrastructure/terraform
    terraform init
    terraform apply
    ```
3.  **Database**:
    Initialize the Cloud SQL database using scripts in `database/`.
4.  **Services**:
    Deploy each service to Cloud Run.
5.  **Client**:
    ```bash
    cd cli-client
    pip install -r requirements.txt
    python main.py
    ```

Details in `walkthrough.md` (Artifacts).