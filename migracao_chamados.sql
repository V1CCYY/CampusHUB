USE campushub;

CREATE TABLE requisicao_itens (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    requisicao_id  INT NOT NULL,
    peca_id        INT NOT NULL,
    quantidade     INT NOT NULL DEFAULT 1,
    CONSTRAINT fk_reqitens_requisicao
        FOREIGN KEY (requisicao_id) REFERENCES requisicoes(id) ON DELETE CASCADE,
    CONSTRAINT fk_reqitens_peca
        FOREIGN KEY (peca_id) REFERENCES pecas(id) ON DELETE CASCADE
) ENGINE=InnoDB;

ALTER TABLE movimentacoes ADD COLUMN requisicao_id INT NULL AFTER peca_id;
ALTER TABLE movimentacoes ADD COLUMN quantidade INT NOT NULL DEFAULT 1 AFTER requisicao_id;
ALTER TABLE movimentacoes ADD CONSTRAINT fk_mov_requisicao
    FOREIGN KEY (requisicao_id) REFERENCES requisicoes(id) ON DELETE SET NULL;
