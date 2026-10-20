-- =====================================================================
-- QR Saathi (powered by Akruthi India) - Migration 001: multi-user accounts
-- ---------------------------------------------------------------------
-- WHAT IT DOES (additive only):
--   * creates 5 NEW tables: users, user_permissions, default_permissions,
--     app_settings, usage_log
--   * adds ONE nullable column `owner_id` (+ index + foreign key) to:
--     batches, vcards, invitations, url_qrs, image_qrs, upi_qrs
--   * seeds the "new user defaults" and the signup setting
--
-- WHAT IT NEVER DOES:
--   * no DROP, no RENAME, no column type change, no DELETE
--   * existing rows, slugs, file names and short links are untouched,
--     so every QR code already printed keeps working
--
-- SAFE TO RE-RUN: every step checks whether it has already been applied.
-- Works on MySQL 5.7 / 8.x and MariaDB 10.3+ (XAMPP).
--
-- HOW TO IMPORT:
--   1. Back up first: phpMyAdmin -> your database -> Export -> Go.
--   2. Select YOUR portal database in the left panel (the one named in
--      DB_NAME in .env), then Import -> choose this file -> Go.
--      (This file deliberately does not contain a USE statement, so it
--      always applies to the database you selected.)
--   3. Start the app. On first boot it creates the admin account from
--      ADMIN_USERNAME / ADMIN_PASSWORD in .env (same login as before) and
--      assigns every existing record to that admin.
-- =====================================================================

SET NAMES utf8mb4;


-- ---------------------------------------------------------------------
-- users : everyone who can sign in. role = 'admin' | 'user'
--         status = 'active' | 'pending' | 'disabled'
--         limit_period = 'lifetime' | 'monthly'
--         total_limit NULL = no overall cap
--         session_version is bumped on password change / disable so
--         existing sessions are signed out.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
    `id`              INT          NOT NULL AUTO_INCREMENT,
    `name`            VARCHAR(150) NOT NULL,
    `username`        VARCHAR(150) NOT NULL,
    `email`           VARCHAR(190) DEFAULT NULL,
    `password_hash`   VARCHAR(255) NOT NULL,
    `role`            VARCHAR(20)  NOT NULL DEFAULT 'user',
    `status`          VARCHAR(20)  NOT NULL DEFAULT 'active',
    `limit_period`    VARCHAR(20)  NOT NULL DEFAULT 'lifetime',
    `total_limit`     INT          DEFAULT NULL,
    `session_version` INT          NOT NULL DEFAULT 1,
    `last_login_at`   DATETIME     DEFAULT NULL,
    `created_at`      DATETIME     DEFAULT NULL,
    `updated_at`      DATETIME     DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_users_username` (`username`),
    UNIQUE KEY `uq_users_email` (`email`),
    KEY `ix_users_role` (`role`),
    KEY `ix_users_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------
-- user_permissions : per-user module access and limit.
--   module : id_cards | vcard | invitation | url_qr | image_qr | upi_qr
--   quota  : NULL = unlimited
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_permissions` (
    `id`      INT         NOT NULL AUTO_INCREMENT,
    `user_id` INT         NOT NULL,
    `module`  VARCHAR(40) NOT NULL,
    `enabled` TINYINT(1)  NOT NULL DEFAULT 1,
    `quota`   INT         DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_user_module` (`user_id`, `module`),
    CONSTRAINT `fk_user_permissions_user`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------
-- default_permissions : what a new account receives at signup.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `default_permissions` (
    `module`  VARCHAR(40) NOT NULL,
    `enabled` TINYINT(1)  NOT NULL DEFAULT 1,
    `quota`   INT         DEFAULT NULL,
    PRIMARY KEY (`module`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------
-- app_settings : simple key/value settings (signup mode, defaults).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `app_settings` (
    `setting_key`   VARCHAR(80)  NOT NULL,
    `setting_value` VARCHAR(255) DEFAULT NULL,
    PRIMARY KEY (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------
-- usage_log : one row each time a user creates a QR / generates a card.
--             Drives monthly limits and usage history.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `usage_log` (
    `id`         INT         NOT NULL AUTO_INCREMENT,
    `user_id`    INT         NOT NULL,
    `module`     VARCHAR(40) NOT NULL,
    `created_at` DATETIME    DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `ix_usage_user_module_time` (`user_id`, `module`, `created_at`),
    CONSTRAINT `fk_usage_log_user`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------
-- owner_id on the six top-level tables.
-- Each step runs only if it hasn't been applied yet. The column is
-- nullable so existing rows stay valid; the app fills it with the admin's
-- id on first boot. ON DELETE RESTRICT means the database will never
-- silently remove a record because a user row was deleted.
-- (id_cards and vcard_links inherit ownership through their parent.)
-- ---------------------------------------------------------------------

-- batches
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `batches` ADD COLUMN `owner_id` INT NULL DEFAULT NULL',
    'DO 0') FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'batches' AND COLUMN_NAME = 'owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `batches` ADD KEY `ix_batches_owner_id` (`owner_id`)',
    'DO 0') FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'batches' AND INDEX_NAME = 'ix_batches_owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `batches` ADD CONSTRAINT `fk_batches_owner` FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE',
    'DO 0') FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'batches' AND CONSTRAINT_NAME = 'fk_batches_owner');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- vcards
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `vcards` ADD COLUMN `owner_id` INT NULL DEFAULT NULL',
    'DO 0') FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vcards' AND COLUMN_NAME = 'owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `vcards` ADD KEY `ix_vcards_owner_id` (`owner_id`)',
    'DO 0') FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vcards' AND INDEX_NAME = 'ix_vcards_owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `vcards` ADD CONSTRAINT `fk_vcards_owner` FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE',
    'DO 0') FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vcards' AND CONSTRAINT_NAME = 'fk_vcards_owner');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- invitations
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `invitations` ADD COLUMN `owner_id` INT NULL DEFAULT NULL',
    'DO 0') FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'invitations' AND COLUMN_NAME = 'owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `invitations` ADD KEY `ix_invitations_owner_id` (`owner_id`)',
    'DO 0') FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'invitations' AND INDEX_NAME = 'ix_invitations_owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `invitations` ADD CONSTRAINT `fk_invitations_owner` FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE',
    'DO 0') FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'invitations' AND CONSTRAINT_NAME = 'fk_invitations_owner');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- url_qrs
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `url_qrs` ADD COLUMN `owner_id` INT NULL DEFAULT NULL',
    'DO 0') FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'url_qrs' AND COLUMN_NAME = 'owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `url_qrs` ADD KEY `ix_url_qrs_owner_id` (`owner_id`)',
    'DO 0') FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'url_qrs' AND INDEX_NAME = 'ix_url_qrs_owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `url_qrs` ADD CONSTRAINT `fk_url_qrs_owner` FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE',
    'DO 0') FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'url_qrs' AND CONSTRAINT_NAME = 'fk_url_qrs_owner');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- image_qrs
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `image_qrs` ADD COLUMN `owner_id` INT NULL DEFAULT NULL',
    'DO 0') FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'image_qrs' AND COLUMN_NAME = 'owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `image_qrs` ADD KEY `ix_image_qrs_owner_id` (`owner_id`)',
    'DO 0') FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'image_qrs' AND INDEX_NAME = 'ix_image_qrs_owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `image_qrs` ADD CONSTRAINT `fk_image_qrs_owner` FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE',
    'DO 0') FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'image_qrs' AND CONSTRAINT_NAME = 'fk_image_qrs_owner');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- upi_qrs
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `upi_qrs` ADD COLUMN `owner_id` INT NULL DEFAULT NULL',
    'DO 0') FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'upi_qrs' AND COLUMN_NAME = 'owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `upi_qrs` ADD KEY `ix_upi_qrs_owner_id` (`owner_id`)',
    'DO 0') FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'upi_qrs' AND INDEX_NAME = 'ix_upi_qrs_owner_id');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @s := (SELECT IF(COUNT(*) = 0,
    'ALTER TABLE `upi_qrs` ADD CONSTRAINT `fk_upi_qrs_owner` FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE',
    'DO 0') FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'upi_qrs' AND CONSTRAINT_NAME = 'fk_upi_qrs_owner');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- ---------------------------------------------------------------------
-- Seed: new user defaults + signup setting.
-- INSERT IGNORE keeps any value the admin has already changed.
-- quota NULL = unlimited. All of this is editable later in
-- Admin -> Settings.
-- ---------------------------------------------------------------------
INSERT IGNORE INTO `default_permissions` (`module`, `enabled`, `quota`) VALUES
    ('id_cards',   1, 25),
    ('vcard',      1, 10),
    ('invitation', 1, 10),
    ('url_qr',     1, 10),
    ('image_qr',   1, 10),
    ('upi_qr',     1, 10);

-- signup_mode: 'approval' (admin approves new accounts) | 'open' | 'closed'
INSERT IGNORE INTO `app_settings` (`setting_key`, `setting_value`) VALUES
    ('signup_mode',           'approval'),
    ('default_limit_period',  'lifetime'),
    ('default_total_limit',   NULL);

-- Done. Start the app to create the admin account and assign existing data.
