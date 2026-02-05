-- ACQUIRE QUOTA (with locking to prevent races)
CREATE OR REPLACE FUNCTION acquire_quota(
    p_date DATE,
    p_max INTEGER,
    p_transaction_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_used INTEGER;
BEGIN
    -- Insert if not exists
    INSERT INTO daily_quota (quota_date, max_discounts)
    VALUES (p_date, p_max)
    ON CONFLICT (quota_date) DO NOTHING;
    
    -- Lock row and check
    SELECT discounts_used INTO v_used
    FROM daily_quota
    WHERE quota_date = p_date
    FOR UPDATE;  -- Critical: prevents race conditions
    
    IF v_used < p_max THEN
        -- Increment
        UPDATE daily_quota 
        SET discounts_used = discounts_used + 1
        WHERE quota_date = p_date;
        
        -- Record allocation
        INSERT INTO quota_allocations (transaction_id, quota_date)
        VALUES (p_transaction_id, p_date);
        
        RETURN TRUE;
    END IF;
    
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- RELEASE QUOTA (compensation)
CREATE OR REPLACE FUNCTION release_quota(
    p_transaction_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_date DATE;
    v_released BOOLEAN;
BEGIN
    SELECT quota_date, released INTO v_date, v_released
    FROM quota_allocations
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;
    
    IF NOT FOUND OR v_released THEN
        RETURN FALSE;
    END IF;
    
    -- Decrement
    UPDATE daily_quota 
    SET discounts_used = discounts_used - 1
    WHERE quota_date = v_date;
    
    -- Mark released
    UPDATE quota_allocations
    SET released = TRUE, released_at = NOW()
    WHERE transaction_id = p_transaction_id;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;
