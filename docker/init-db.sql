-- Smart AI Tutor PostgreSQL Schema
-- Phase 2: Database Migration

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    phone_number VARCHAR(50),
    role VARCHAR(50) DEFAULT 'User',
    theme VARCHAR(20) DEFAULT 'light',
    notes TEXT,
    profile_picture_path VARCHAR(500),

    -- Security fields
    is_locked BOOLEAN DEFAULT FALSE,
    locked_until TIMESTAMP,
    login_attempts INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,

    -- Indexes for fast lookups
    CONSTRAINT users_email_check CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

-- Create indexes
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created_at ON users(created_at DESC);

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE
    ON users FOR EACH ROW
    EXECUTE PROCEDURE update_updated_at_column();

-- Quiz results table (for local storage, chat sessions will be in DynamoDB)
CREATE TABLE IF NOT EXISTS quiz_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    quiz_id VARCHAR(255) NOT NULL,
    score FLOAT NOT NULL,
    total_questions INTEGER NOT NULL,
    correct_answers INTEGER NOT NULL,
    time_taken_seconds INTEGER,
    quiz_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Composite index for user quiz history
    CONSTRAINT quiz_results_score_check CHECK (score >= 0 AND score <= 100)
);

CREATE INDEX idx_quiz_results_username ON quiz_results(username);
CREATE INDEX idx_quiz_results_created_at ON quiz_results(created_at DESC);
CREATE INDEX idx_quiz_results_quiz_id ON quiz_results(quiz_id);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO smart_tutor_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO smart_tutor_user;
