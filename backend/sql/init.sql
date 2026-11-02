-- À exécuter une fois dans phpMyAdmin (XAMPP) en root : base + utilisateur à privilèges minimaux
CREATE DATABASE IF NOT EXISTS flux_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'flux_user'@'localhost' IDENTIFIED BY 'CHANGE_ME';
CREATE USER IF NOT EXISTS 'flux_user'@'127.0.0.1' IDENTIFIED BY 'CHANGE_ME';
-- Moindre privilège : CRUD + création de tables (retirer CREATE/ALTER/INDEX après la mise en place)
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES ON flux_db.* TO 'flux_user'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES ON flux_db.* TO 'flux_user'@'127.0.0.1';
FLUSH PRIVILEGES;
