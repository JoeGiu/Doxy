-- init_db.sql
-- Script di inizializzazione del database per Doxy WebApp
-- Eseguire: mysql -u root -p doxy_db < init_db.sql

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- ── utente ──────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS `utente` (
  `id_utente`            BIGINT       NOT NULL,
  `codice_fiscale`       VARCHAR(255) DEFAULT NULL,
  `cognome`              VARCHAR(255) DEFAULT NULL,
  `data_nascita`         VARCHAR(255) DEFAULT NULL,
  `email`                VARCHAR(255) DEFAULT NULL,
  `indirizzo_domicilio`  VARCHAR(255) DEFAULT NULL,
  `indirizzo_residenza`  VARCHAR(255) DEFAULT NULL,
  `localita_domicilio`   VARCHAR(255) DEFAULT NULL,
  `localita_nascita`     VARCHAR(255) DEFAULT NULL,
  `localita_residenza`   VARCHAR(255) DEFAULT NULL,
  `matricola`            VARCHAR(255) DEFAULT NULL,
  `nome`                 VARCHAR(255) DEFAULT NULL,
  `password`             VARCHAR(255) DEFAULT NULL,
  `telefono`             VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`id_utente`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Utente admin iniziale (email: giuseppe.battista74@gmail.com / password: BATTIGIUPPE)
INSERT IGNORE INTO `utente`
  (id_utente, nome, cognome, email, password, matricola, codice_fiscale,
   data_nascita, indirizzo_residenza, localita_residenza,
   indirizzo_domicilio, localita_domicilio, localita_nascita, telefono)
VALUES
  (1, 'Giuseppe', 'Battista', 'giuseppe.battista74@gmail.com', 'BATTIGIUPPE',
   '001', 'BTTGPP74A01H703X', '01/01/1974', 'Via Roma 1', 'Napoli',
   'Via Roma 1', 'Napoli', 'Napoli', '3331234567');

-- ── articolo ────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS `articolo` (
  `id_articolo`  BIGINT       NOT NULL,
  `codice`       VARCHAR(255) DEFAULT NULL,
  `descrizione`  VARCHAR(255) DEFAULT NULL,
  `giacenza`     BIGINT       DEFAULT NULL,
  `quantita`     BIGINT       DEFAULT NULL,
  `unita_misura` VARCHAR(255) DEFAULT NULL,
  `valore`       BIGINT       DEFAULT NULL,
  PRIMARY KEY (`id_articolo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── fornitore ───────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS `fornitore` (
  `id_fornitore`   BIGINT       NOT NULL,
  `citta`          VARCHAR(255) DEFAULT NULL,
  `codice_fiscale` VARCHAR(255) DEFAULT NULL,
  `email`          VARCHAR(255) DEFAULT NULL,
  `indirizzo`      VARCHAR(255) DEFAULT NULL,
  `matricola`      VARCHAR(255) DEFAULT NULL,
  `p_iva`          VARCHAR(255) DEFAULT NULL,
  `ragione_sociale` VARCHAR(255) DEFAULT NULL,
  `telefono`       VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`id_fornitore`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── veicolo ─────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS `veicolo` (
  `id_veicolo`           BIGINT       NOT NULL,
  `data_immatricolazione` VARCHAR(255) DEFAULT NULL,
  `matricola`            VARCHAR(255) DEFAULT NULL,
  `modello`              VARCHAR(255) DEFAULT NULL,
  `numero_telaio`        VARCHAR(255) DEFAULT NULL,
  `targa`                VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`id_veicolo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── ddt ─────────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS `ddt` (
  `id_ddt`       BIGINT       NOT NULL,
  `data_ddt`     VARCHAR(255) DEFAULT NULL,
  `numero_ddt`   VARCHAR(255) DEFAULT NULL,
  `id_fornitore` BIGINT       DEFAULT NULL,
  PRIMARY KEY (`id_ddt`),
  CONSTRAINT `fk_ddt_fornitore`
    FOREIGN KEY (`id_fornitore`) REFERENCES `fornitore` (`id_fornitore`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── corpo_documento ─────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS `corpo_documento` (
  `id_corpo_documento` BIGINT NOT NULL,
  `id_articolo`        BIGINT DEFAULT NULL,
  `id_ddt`             BIGINT DEFAULT NULL,
  `quantita`           BIGINT DEFAULT 1,
  PRIMARY KEY (`id_corpo_documento`),
  CONSTRAINT `fk_corpo_ddt`
    FOREIGN KEY (`id_ddt`)      REFERENCES `ddt`      (`id_ddt`),
  CONSTRAINT `fk_corpo_articolo`
    FOREIGN KEY (`id_articolo`) REFERENCES `articolo` (`id_articolo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── commessa ────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS `commessa` (
  `id_commessa`       BIGINT       NOT NULL,
  `numero_commessa`   VARCHAR(255) NOT NULL,
  `data_entrata`      VARCHAR(255) DEFAULT NULL,
  `data_uscita`       VARCHAR(255) DEFAULT NULL,
  `id_veicolo`        BIGINT       DEFAULT NULL,
  `descrizione_lavori` TEXT        DEFAULT NULL,
  PRIMARY KEY (`id_commessa`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── commessa_articolo ───────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS `commessa_articolo` (
  `id_commessa_articolo` BIGINT NOT NULL,
  `id_commessa`          BIGINT DEFAULT NULL,
  `id_articolo`          BIGINT DEFAULT NULL,
  `quantita`             BIGINT DEFAULT 1,
  PRIMARY KEY (`id_commessa_articolo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── autista ─────────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS `autista` (
  `id_autista` BIGINT       NOT NULL,
  `nome`       VARCHAR(255) NOT NULL,
  `cognome`    VARCHAR(255) NOT NULL,
  `email`      VARCHAR(255) NOT NULL,
  `password`   VARCHAR(255) NOT NULL,
  `telefono`   VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`id_autista`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── segnalazione ────────────────────────────────────────────────────────── --
CREATE TABLE IF NOT EXISTS `segnalazione` (
  `id_segnalazione`   BIGINT        NOT NULL,
  `id_autista`        BIGINT        NOT NULL,
  `id_veicolo`        BIGINT        NOT NULL,
  `descrizione`       TEXT          NOT NULL,
  `foto_path`         VARCHAR(500)  DEFAULT NULL,
  `data_segnalazione` DATETIME      DEFAULT CURRENT_TIMESTAMP,
  `stato`             VARCHAR(50)   DEFAULT 'nuova',
  `letta`             TINYINT(1)    DEFAULT 0,
  PRIMARY KEY (`id_segnalazione`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
