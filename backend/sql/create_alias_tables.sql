-- 项目别名自动学习系统表结构
-- 执行时间：2026-05-06

-- 1. 用户纠正记录表
CREATE TABLE IF NOT EXISTS project_corrections (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    original_hint VARCHAR(200),
    original_match VARCHAR(200),
    corrected_project_id INTEGER,
    confidence_before DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_corrections_hint 
ON project_corrections(original_hint);

CREATE INDEX IF NOT EXISTS idx_corrections_project 
ON project_corrections(corrected_project_id);

CREATE INDEX IF NOT EXISTS idx_corrections_created 
ON project_corrections(created_at);


-- 2. 项目别名知识库
CREATE TABLE IF NOT EXISTS project_alias (
    id SERIAL PRIMARY KEY,
    alias_name VARCHAR(200) UNIQUE NOT NULL,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    source VARCHAR(20) DEFAULT 'manual',
    confidence DECIMAL(3,2) DEFAULT 0.9,
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(50),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_alias_name 
ON project_alias(alias_name);

CREATE INDEX IF NOT EXISTS idx_alias_project 
ON project_alias(project_id);

CREATE INDEX IF NOT EXISTS idx_alias_active 
ON project_alias(is_active);


-- 3. 别名使用日志
CREATE TABLE IF NOT EXISTS alias_usage_log (
    id SERIAL PRIMARY KEY,
    alias_name VARCHAR(200),
    project_id INTEGER,
    matched_method VARCHAR(20),
    confidence DECIMAL(3,2),
    user_feedback BOOLEAN,
    report_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_log_alias 
ON alias_usage_log(alias_name);

CREATE INDEX IF NOT EXISTS idx_usage_log_created 
ON alias_usage_log(created_at);