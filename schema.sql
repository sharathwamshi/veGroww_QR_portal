-- =====================================================================
-- QR Saathi (powered by Akruthi India) - MySQL schema (import-ready)
--
-- Import via CLI:
--     mysql -u root -p < schema.sql
--
-- Import via phpMyAdmin / MySQL Workbench / HeidiSQL:
--     Just choose this file in Import. It creates the database itself,
--     so you do NOT need to pre-select one. If your hosting panel does
--     not allow CREATE DATABASE, comment out the two lines marked
--     [PANEL] below, select your database first, then import.
--
-- FRESH INSTALL: import this file, THEN import
-- migrations/001_multi_user_accounts.sql, which adds the user-account
-- tables and the owner column. Together they mirror models/ exactly, so
-- the app runs with AUTO_CREATE_TABLES=0 in .env.
--
-- EXISTING INSTALL: do NOT re-import this file. Only import the migration.
-- =====================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';

-- [PANEL] ------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS `vegroww_qr_portal`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;
USE `vegroww_qr_portal`;
-- ---------------------------------------------------------------------


-- ---------------------------------------------------------------------
-- batches : one company identity (name / address / logo / signature)
--           shared by every ID card generated inside it.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `batches` (
    `id`                 INT           NOT NULL AUTO_INCREMENT,
    `name`               VARCHAR(150)  NOT NULL,
    `company_name`       VARCHAR(200)  NOT NULL,
    `company_address`    VARCHAR(400)  NOT NULL,
    `logo_filename`      VARCHAR(255)  DEFAULT NULL,
    `signature_filename` VARCHAR(255)  DEFAULT NULL,
    `signature_label`    VARCHAR(150)  DEFAULT 'Issuing Authority',
    `created_at`         DATETIME      DEFAULT NULL,
    `updated_at`         DATETIME      DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `ix_batches_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ---------------------------------------------------------------------
-- id_cards : one employee entry per row.
--   status: 'pending_photo' -> no photo yet
--           'ready'         -> photo uploaded, card not rendered
--           'generated'     -> card image + QR produced
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `id_cards` (
    `id`                INT          NOT NULL AUTO_INCREMENT,
    `batch_id`          INT          NOT NULL,
    `sr_no`             INT          DEFAULT NULL,
    `name`              VARCHAR(150) NOT NULL,
    `employee_code`     VARCHAR(50)  NOT NULL,
    `designation`       VARCHAR(150) DEFAULT NULL,
    `blood_group`       VARCHAR(10)  DEFAULT NULL,
    `landline`          VARCHAR(30)  DEFAULT NULL,
    `emergency_contact` VARCHAR(20)  DEFAULT NULL,
    `employee_contact`  VARCHAR(20)  DEFAULT NULL,
    `email`             VARCHAR(150) DEFAULT NULL,
    `photo_filename`    VARCHAR(255) DEFAULT NULL,
    `card_filename`     VARCHAR(255) DEFAULT NULL,
    `qr_filename`       VARCHAR(255) DEFAULT NULL,
    `qr_short_url`      VARCHAR(500) DEFAULT NULL,
    `qr_target_url`     VARCHAR(500) DEFAULT NULL,
    `status`            VARCHAR(20)  NOT NULL DEFAULT 'pending_photo',
    `created_at`        DATETIME     DEFAULT NULL,
    `updated_at`        DATETIME     DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_batch_employee_code` (`batch_id`, `employee_code`),
    KEY `ix_id_cards_employee_code` (`employee_code`),
    KEY `ix_id_cards_status` (`status`),
    CONSTRAINT `fk_id_cards_batch`
        FOREIGN KEY (`batch_id`) REFERENCES `batches` (`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ---------------------------------------------------------------------
-- image_qrs : uploaded image + the QR code that opens it.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `image_qrs` (
    `id`             INT          NOT NULL AUTO_INCREMENT,
    `title`          VARCHAR(150) NOT NULL,
    `image_filename` VARCHAR(255) NOT NULL,
    `qr_filename`    VARCHAR(255) NOT NULL,
    `target_url`     VARCHAR(500) NOT NULL,
    `short_url`      VARCHAR(500) DEFAULT NULL,
    `created_at`     DATETIME     DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `ix_image_qrs_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ---------------------------------------------------------------------
-- upi_qrs : generated upi://pay deep-link QR codes.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `upi_qrs` (
    `id`          INT            NOT NULL AUTO_INCREMENT,
    `upi_id`      VARCHAR(150)   NOT NULL,
    `payee_name`  VARCHAR(150)   DEFAULT NULL,
    `amount`      DECIMAL(10, 2) DEFAULT NULL,
    `note`        VARCHAR(200)   DEFAULT NULL,
    `upi_uri`     VARCHAR(500)   NOT NULL,
    `qr_filename` VARCHAR(255)   NOT NULL,
    `created_at`  DATETIME       DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `ix_upi_qrs_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ---------------------------------------------------------------------
-- vcards : one digital business card. Drives the public page at
--          /vcard/v/<slug> and the QR code that opens it.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `vcards` (
    `id`               INT          NOT NULL AUTO_INCREMENT,
    `slug`             VARCHAR(80)  NOT NULL,
    `qr_name`          VARCHAR(150) NOT NULL,
    `primary_color`    VARCHAR(7)   NOT NULL DEFAULT '#527AC9',
    `secondary_color`  VARCHAR(7)   NOT NULL DEFAULT '#7EC09F',
    `first_name`       VARCHAR(100) NOT NULL,
    `last_name`        VARCHAR(100) DEFAULT NULL,
    `image_filename`   VARCHAR(255) DEFAULT NULL,
    `company`          VARCHAR(200) DEFAULT NULL,
    `profession`       VARCHAR(200) DEFAULT NULL,
    `summary`          TEXT         DEFAULT NULL,
    `address_line`     VARCHAR(300) DEFAULT NULL,
    `city`             VARCHAR(120) DEFAULT NULL,
    `state`            VARCHAR(120) DEFAULT NULL,
    `postal_code`      VARCHAR(20)  DEFAULT NULL,
    `country`          VARCHAR(120) DEFAULT NULL,
    `show_add_contact` TINYINT(1)   NOT NULL DEFAULT 1,
    `qr_filename`      VARCHAR(255) DEFAULT NULL,
    `qr_target_url`    VARCHAR(500) DEFAULT NULL,
    `qr_short_url`     VARCHAR(500) DEFAULT NULL,
    `created_at`       DATETIME     DEFAULT NULL,
    `updated_at`       DATETIME     DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_vcards_slug` (`slug`),
    KEY `ix_vcards_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ---------------------------------------------------------------------
-- vcard_links : repeatable entries on a vCard.
--   kind: 'phone' | 'email' | 'website' | 'social'
--   platform is only set for 'social' rows (instagram, linkedin, ...).
--   sort_order preserves the display order chosen in the builder.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `vcard_links` (
    `id`         INT          NOT NULL AUTO_INCREMENT,
    `vcard_id`   INT          NOT NULL,
    `kind`       VARCHAR(20)  NOT NULL,
    `platform`   VARCHAR(40)  DEFAULT NULL,
    `value`      VARCHAR(500) NOT NULL,
    `label`      VARCHAR(100) DEFAULT NULL,
    `sort_order` INT          NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    KEY `ix_vcard_links_vcard_id` (`vcard_id`),
    KEY `ix_vcard_links_kind` (`kind`),
    CONSTRAINT `fk_vcard_links_vcard`
        FOREIGN KEY (`vcard_id`) REFERENCES `vcards` (`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ---------------------------------------------------------------------
-- url_qrs : QR codes pointing at any external web address.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `url_qrs` (
    `id`          INT           NOT NULL AUTO_INCREMENT,
    `name`        VARCHAR(150)  NOT NULL,
    `target_url`  VARCHAR(1000) NOT NULL,
    `short_url`   VARCHAR(500)  DEFAULT NULL,
    `qr_filename` VARCHAR(255)  NOT NULL,
    `created_at`  DATETIME      DEFAULT NULL,
    `updated_at`  DATETIME      DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `ix_url_qrs_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ---------------------------------------------------------------------
-- invitations : digital invitation cards.
--   host_details_json holds the per-event-type name fields (bride/groom,
--   baby name, etc.) as JSON, so adding a new event type needs no
--   migration — see utils/event_types.py for the field definitions.
--   secondary_* is the second session; only weddings use it.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `invitations` (
    `id`                INT          NOT NULL AUTO_INCREMENT,
    `slug`              VARCHAR(80)  NOT NULL,
    `event_type`        VARCHAR(40)  NOT NULL,
    `title`             VARCHAR(200) NOT NULL,
    `host_details_json` TEXT         DEFAULT NULL,
    `primary_label`     VARCHAR(120) DEFAULT NULL,
    `primary_start`     DATETIME     NOT NULL,
    `primary_end`       DATETIME     DEFAULT NULL,
    `secondary_label`   VARCHAR(120) DEFAULT NULL,
    `secondary_start`   DATETIME     DEFAULT NULL,
    `secondary_end`     DATETIME     DEFAULT NULL,
    `venue_name`        VARCHAR(200) NOT NULL,
    `venue_address`     VARCHAR(500) DEFAULT NULL,
    `map_url`           VARCHAR(700) DEFAULT NULL,
    `latitude`          DOUBLE       DEFAULT NULL,
    `longitude`         DOUBLE       DEFAULT NULL,
    `message`           TEXT         DEFAULT NULL,
    `rsvp_phone`        VARCHAR(30)  DEFAULT NULL,
    `rsvp_whatsapp`     VARCHAR(30)  DEFAULT NULL,
    `dress_code`        VARCHAR(150) DEFAULT NULL,
    `hero_filename`     VARCHAR(255) DEFAULT NULL,
    `primary_color`     VARCHAR(7)   NOT NULL DEFAULT '#8C1D40',
    `secondary_color`   VARCHAR(7)   NOT NULL DEFAULT '#D4A15E',
    `qr_filename`       VARCHAR(255) DEFAULT NULL,
    `qr_target_url`     VARCHAR(500) DEFAULT NULL,
    `qr_short_url`      VARCHAR(500) DEFAULT NULL,
    `created_at`        DATETIME     DEFAULT NULL,
    `updated_at`        DATETIME     DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_invitations_slug` (`slug`),
    KEY `ix_invitations_event_type` (`event_type`),
    KEY `ix_invitations_primary_start` (`primary_start`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


SET FOREIGN_KEY_CHECKS = 1;
