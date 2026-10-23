-- 2026-10: 私钥改为加密存储后长度超出 VARCHAR(2000)，扩为 TEXT
-- 已有数据库执行；新库由 create_all 自动使用 TEXT
ALTER TABLE products MODIFY COLUMN private_key TEXT NOT NULL COMMENT 'RSA私钥（Fernet加密）';
