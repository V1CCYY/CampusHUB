-- Rode UMA vez no MySQL Workbench se o banco já existe (instalações novas via database.sql já têm a coluna).
USE campushub;

ALTER TABLE requisicoes
    ADD COLUMN sala_id INT NULL AFTER solicitante_id,
    ADD CONSTRAINT fk_requisicoes_sala
        FOREIGN KEY (sala_id) REFERENCES salas(id) ON DELETE SET NULL;
