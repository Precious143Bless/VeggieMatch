
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ── django_migrations ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `django_migrations` (
  `id`      bigint       NOT NULL AUTO_INCREMENT,
  `app`     varchar(255) NOT NULL,
  `name`    varchar(255) NOT NULL,
  `applied` datetime(6)  NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── django_content_type ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS `django_content_type` (
  `id`        int          NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model`     varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_content_type` (`app_label`, `model`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── django_session ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `django_session` (
  `session_key`  varchar(40)  NOT NULL,
  `session_data` longtext     NOT NULL,
  `expire_date`  datetime(6)  NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `idx_session_expire` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── core_vegetablepost ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `core_vegetablepost` (
  `id`              bigint        NOT NULL AUTO_INCREMENT,
  `farmer_name`     varchar(100)  NOT NULL,
  `phone_number`    varchar(20)   NOT NULL,
  `farmer_photo`    varchar(100)  DEFAULT NULL,
  `vegetable`       varchar(100)  NOT NULL,
  `veggie_photo`    varchar(100)  DEFAULT NULL,
  `surplus_level`   varchar(10)   NOT NULL DEFAULT 'LOW',
  `quantity`        decimal(8,2)  NOT NULL,
  `price_per_kg`    decimal(8,2)  NOT NULL DEFAULT '1.00',
  `pickup_address`  varchar(255)  NOT NULL DEFAULT 'La Trinidad Trading Post, Benguet',
  `pickup_note`     varchar(255)  NOT NULL DEFAULT '',
  -- status: ACTIVE | BOUGHT (paid) | CLAIMED (donated, fully taken) | RESCUE (available to donate)
  `status`          varchar(10)   NOT NULL DEFAULT 'ACTIVE',
  `created_at`      datetime(6)   NOT NULL,
  `expiry_time`     datetime(6)   NOT NULL,
  `expiry_notified` tinyint(1)    NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_post_status`  (`status`),
  KEY `idx_post_expiry`  (`expiry_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── core_buyrecord ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `core_buyrecord` (
  `id`           bigint        NOT NULL AUTO_INCREMENT,
  `post_id`      bigint        NOT NULL,
  `buyer_name`   varchar(100)  NOT NULL,
  `buyer_number` varchar(20)   NOT NULL,
  `buyer_photo`  varchar(100)  DEFAULT NULL,
  `quantity_kg`  decimal(8,2)  NOT NULL DEFAULT '0.00',
  `bought_at`    datetime(6)   NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_buy_post` (`post_id`),
  CONSTRAINT `fk_buy_post` FOREIGN KEY (`post_id`) REFERENCES `core_vegetablepost` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── core_rescuerecord ─────────────────────────────────────────
-- Multiple claimers can take partial quantities from one donated post
CREATE TABLE IF NOT EXISTS `core_rescuerecord` (
  `id`              bigint        NOT NULL AUTO_INCREMENT,
  `post_id`         bigint        NOT NULL,
  `claimer_name`    varchar(100)  NOT NULL,
  `claimer_number`  varchar(20)   NOT NULL,
  `claimer_photo`   varchar(100)  DEFAULT NULL,
  `quantity_kg`     decimal(8,2)  NOT NULL DEFAULT '0.00',
  `claimed_at`      datetime(6)   NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_rescue_post` (`post_id`),
  CONSTRAINT `fk_rescue_post` FOREIGN KEY (`post_id`) REFERENCES `core_vegetablepost` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── core_otpverification ──────────────────────────────────────
-- purpose: POST | BUY | RESCUE | DONATE | EDIT | DELETE
CREATE TABLE IF NOT EXISTS `core_otpverification` (
  `id`           bigint      NOT NULL AUTO_INCREMENT,
  `phone_number` varchar(20) NOT NULL,
  `otp_code`     varchar(6)  NOT NULL,
  `purpose`      varchar(10) NOT NULL,
  `post_id`      bigint      DEFAULT NULL,
  `created_at`   datetime(6) NOT NULL,
  `expires_at`   datetime(6) NOT NULL,
  `is_used`      tinyint(1)  NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_otp_phone_purpose` (`phone_number`, `purpose`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Mark all migrations as applied ───────────────────────────
INSERT IGNORE INTO `django_migrations` (`app`, `name`, `applied`) VALUES
  ('contenttypes', '0001_initial',                  NOW()),
  ('contenttypes', '0002_remove_content_type_name', NOW()),
  ('sessions',     '0001_initial',                  NOW()),
  ('core',         '0001_initial',                  NOW());

SET FOREIGN_KEY_CHECKS = 1;
