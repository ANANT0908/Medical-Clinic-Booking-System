-- SERVICES TABLE
CREATE TABLE services (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    gender VARCHAR(10) CHECK (gender IN ('male', 'female', 'both')),
    base_price DECIMAL(10, 2) CHECK (base_price > 0),
    description TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO services (name, gender, base_price) VALUES
('General Consultation', 'both', 300.00),
('Gynecology', 'female', 500.00),
('Ultrasound', 'female', 800.00),
('Blood Test', 'both', 450.00),
('Cardiology', 'both', 600.00),
('Urology', 'male', 550.00),
('Prostate Screening', 'male', 700.00),
('Dermatology', 'both', 400.00);

-- BOOKINGS TABLE
CREATE TABLE bookings (
    id SERIAL PRIMARY KEY,
    transaction_id UUID UNIQUE NOT NULL,
    user_name VARCHAR(255),
    user_gender VARCHAR(10),
    user_dob DATE,
    service_ids INTEGER[],
    base_price DECIMAL(10, 2),
    discount_applied BOOLEAN,
    discount_percentage DECIMAL(5, 2),
    final_price DECIMAL(10, 2),
    booking_status VARCHAR(50),
    reference_id VARCHAR(50) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- QUOTA TABLE (critical for R2)
CREATE TABLE daily_quota (
    id SERIAL PRIMARY KEY,
    quota_date DATE UNIQUE NOT NULL,
    discounts_used INTEGER DEFAULT 0 CHECK (discounts_used >= 0),
    max_discounts INTEGER NOT NULL DEFAULT 100,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- QUOTA ALLOCATIONS (for tracking)
CREATE TABLE quota_allocations (
    id SERIAL PRIMARY KEY,
    transaction_id UUID NOT NULL,
    quota_date DATE NOT NULL,
    allocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    released BOOLEAN DEFAULT FALSE,
    released_at TIMESTAMP
);

-- TRANSACTION EVENTS (audit log)
CREATE TABLE transaction_events (
    id SERIAL PRIMARY KEY,
    transaction_id UUID,
    event_type VARCHAR(100),
    event_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TRANSACTION STATE (for orchestrator)
CREATE TABLE transaction_state (
    transaction_id UUID PRIMARY KEY,
    current_state VARCHAR(50),
    user_data JSONB,
    pricing_data JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
