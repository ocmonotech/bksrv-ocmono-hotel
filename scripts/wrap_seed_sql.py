from pathlib import Path

path = Path(__file__).resolve().parents[2] / "database" / "restrochain.sql"
body = path.read_text(encoding="utf-8-sig")

header = """-- RestroChain OS — single demo database file
-- Contains ALL mock/demo data for a fresh install.
--
-- Load AFTER Alembic migrations create the schema:
--   mysql -u restrochain -p restrochain_db < database/restrochain.sql
--
-- Demo login: admin@restrochain.test / Admin@123
--
-- Regenerated from a seeded Docker MySQL instance (data only, no CREATE TABLE).

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

CREATE DATABASE IF NOT EXISTS restrochain_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE restrochain_db;

SET FOREIGN_KEY_CHECKS=0;
SET UNIQUE_CHECKS=0;
SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';

"""

footer = """
SET FOREIGN_KEY_CHECKS=1;
SET UNIQUE_CHECKS=1;
"""

path.write_text(header + body + footer, encoding="utf-8")
print(f"wrote {path} ({path.stat().st_size} bytes, {body.count('INSERT INTO')} inserts)")
