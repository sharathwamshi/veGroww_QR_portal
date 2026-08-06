SET FOREIGN_KEY_CHECKS = 0;

DROP DATABASE IF EXISTS `vegroww_qr_portal`;
CREATE DATABASE `vegroww_qr_portal` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `vegroww_qr_portal`;

DROP TABLE IF EXISTS `vcard_links`;
DROP TABLE IF EXISTS `id_cards`;
DROP TABLE IF EXISTS `invitations`;
DROP TABLE IF EXISTS `url_qrs`;
DROP TABLE IF EXISTS `upi_qrs`;
DROP TABLE IF EXISTS `image_qrs`;
DROP TABLE IF EXISTS `vcards`;
DROP TABLE IF EXISTS `batches`;

CREATE TABLE `batches` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(150) NOT NULL,
  `company_name` VARCHAR(200) NOT NULL,
  `company_address` VARCHAR(400) NOT NULL,
  `logo_filename` VARCHAR(255) DEFAULT NULL,
  `signature_filename` VARCHAR(255) DEFAULT NULL,
  `signature_label` VARCHAR(150) DEFAULT 'Issuing Authority',
  `created_at` DATETIME DEFAULT NULL,
  `updated_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_batches_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `id_cards` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `batch_id` INT NOT NULL,
  `sr_no` INT DEFAULT NULL,
  `name` VARCHAR(150) NOT NULL,
  `employee_code` VARCHAR(50) NOT NULL,
  `designation` VARCHAR(150) DEFAULT NULL,
  `blood_group` VARCHAR(10) DEFAULT NULL,
  `landline` VARCHAR(30) DEFAULT NULL,
  `emergency_contact` VARCHAR(20) DEFAULT NULL,
  `employee_contact` VARCHAR(20) DEFAULT NULL,
  `email` VARCHAR(150) DEFAULT NULL,
  `photo_filename` VARCHAR(255) DEFAULT NULL,
  `card_filename` VARCHAR(255) DEFAULT NULL,
  `qr_filename` VARCHAR(255) DEFAULT NULL,
  `qr_short_url` VARCHAR(500) DEFAULT NULL,
  `qr_target_url` VARCHAR(500) DEFAULT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending_photo',
  `created_at` DATETIME DEFAULT NULL,
  `updated_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_batch_employee_code` (`batch_id`,`employee_code`),
  KEY `ix_id_cards_batch_id` (`batch_id`),
  KEY `ix_id_cards_employee_code` (`employee_code`),
  KEY `ix_id_cards_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `image_qrs` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(150) NOT NULL,
  `image_filename` VARCHAR(255) NOT NULL,
  `qr_filename` VARCHAR(255) NOT NULL,
  `target_url` VARCHAR(500) NOT NULL,
  `short_url` VARCHAR(500) DEFAULT NULL,
  `created_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_image_qrs_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `upi_qrs` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `upi_id` VARCHAR(150) NOT NULL,
  `payee_name` VARCHAR(150) DEFAULT NULL,
  `amount` DECIMAL(10,2) DEFAULT NULL,
  `note` VARCHAR(200) DEFAULT NULL,
  `upi_uri` VARCHAR(500) NOT NULL,
  `qr_filename` VARCHAR(255) NOT NULL,
  `created_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_upi_qrs_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `url_qrs` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(150) NOT NULL,
  `target_url` VARCHAR(1000) NOT NULL,
  `short_url` VARCHAR(500) DEFAULT NULL,
  `qr_filename` VARCHAR(255) NOT NULL,
  `created_at` DATETIME DEFAULT NULL,
  `updated_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_url_qrs_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `vcards` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `slug` VARCHAR(80) NOT NULL,
  `qr_name` VARCHAR(150) NOT NULL,
  `primary_color` VARCHAR(7) NOT NULL DEFAULT '#527AC9',
  `secondary_color` VARCHAR(7) NOT NULL DEFAULT '#7EC09F',
  `first_name` VARCHAR(100) NOT NULL,
  `last_name` VARCHAR(100) DEFAULT NULL,
  `image_filename` VARCHAR(255) DEFAULT NULL,
  `company` VARCHAR(200) DEFAULT NULL,
  `profession` VARCHAR(200) DEFAULT NULL,
  `summary` TEXT DEFAULT NULL,
  `address_line` VARCHAR(300) DEFAULT NULL,
  `city` VARCHAR(120) DEFAULT NULL,
  `state` VARCHAR(120) DEFAULT NULL,
  `postal_code` VARCHAR(20) DEFAULT NULL,
  `country` VARCHAR(120) DEFAULT NULL,
  `show_add_contact` TINYINT(1) NOT NULL DEFAULT 1,
  `qr_filename` VARCHAR(255) DEFAULT NULL,
  `qr_target_url` VARCHAR(500) DEFAULT NULL,
  `qr_short_url` VARCHAR(500) DEFAULT NULL,
  `created_at` DATETIME DEFAULT NULL,
  `updated_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_vcards_slug` (`slug`),
  KEY `ix_vcards_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `vcard_links` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `vcard_id` INT NOT NULL,
  `kind` VARCHAR(20) NOT NULL,
  `platform` VARCHAR(40) DEFAULT NULL,
  `value` VARCHAR(500) NOT NULL,
  `label` VARCHAR(100) DEFAULT NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `ix_vcard_links_vcard_id` (`vcard_id`),
  KEY `ix_vcard_links_kind` (`kind`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `invitations` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `slug` VARCHAR(80) NOT NULL,
  `event_type` VARCHAR(40) NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `host_details_json` TEXT DEFAULT NULL,
  `primary_label` VARCHAR(120) DEFAULT NULL,
  `primary_start` DATETIME NOT NULL,
  `primary_end` DATETIME DEFAULT NULL,
  `secondary_label` VARCHAR(120) DEFAULT NULL,
  `secondary_start` DATETIME DEFAULT NULL,
  `secondary_end` DATETIME DEFAULT NULL,
  `venue_name` VARCHAR(200) NOT NULL,
  `venue_address` VARCHAR(500) DEFAULT NULL,
  `map_url` VARCHAR(700) DEFAULT NULL,
  `latitude` DOUBLE DEFAULT NULL,
  `longitude` DOUBLE DEFAULT NULL,
  `message` TEXT DEFAULT NULL,
  `rsvp_phone` VARCHAR(30) DEFAULT NULL,
  `rsvp_whatsapp` VARCHAR(30) DEFAULT NULL,
  `dress_code` VARCHAR(150) DEFAULT NULL,
  `hero_filename` VARCHAR(255) DEFAULT NULL,
  `primary_color` VARCHAR(7) NOT NULL DEFAULT '#8C1D40',
  `secondary_color` VARCHAR(7) NOT NULL DEFAULT '#D4A15E',
  `qr_filename` VARCHAR(255) DEFAULT NULL,
  `qr_target_url` VARCHAR(500) DEFAULT NULL,
  `qr_short_url` VARCHAR(500) DEFAULT NULL,
  `created_at` DATETIME DEFAULT NULL,
  `updated_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_invitations_slug` (`slug`),
  KEY `ix_invitations_event_type` (`event_type`),
  KEY `ix_invitations_primary_start` (`primary_start`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

SET FOREIGN_KEY_CHECKS = 1;
