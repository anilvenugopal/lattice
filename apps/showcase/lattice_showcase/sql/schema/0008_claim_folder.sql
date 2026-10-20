-- Where a claim's documents live on a shared drive, chosen with the folder picker (ADR 0017):
-- "{store}:{path}".

ALTER TABLE showcase.claim ADD COLUMN file_folder varchar(512) NOT NULL DEFAULT '';
