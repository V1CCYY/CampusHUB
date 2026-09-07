
DROP DATABASE IF EXISTS campushub;
CREATE DATABASE campushub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE campushub;

CREATE TABLE usuarios (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    nome          VARCHAR(120)        NOT NULL,
    login         VARCHAR(80)         NOT NULL UNIQUE,
    senha_hash    VARCHAR(255)        NOT NULL,
    cargo         VARCHAR(80)         NOT NULL DEFAULT 'Usuário',
    tipo          ENUM('admin','usuario') NOT NULL DEFAULT 'usuario',
    criado_por    INT NULL,
    ativo         TINYINT(1)          NOT NULL DEFAULT 1,
    data_criacao  DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_usuarios_criado_por
        FOREIGN KEY (criado_por) REFERENCES usuarios(id)
        ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE salas (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nome            VARCHAR(120) NOT NULL,
    tipo            VARCHAR(80)  NULL,
    bloco           VARCHAR(120) NULL,
    computadores    INT          NOT NULL DEFAULT 0,
    responsavel_id  INT NULL,
    status          ENUM('Ativo','Manutenção','Inativo') NOT NULL DEFAULT 'Ativo',
    criado_por      INT NOT NULL,
    data_criacao    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_salas_responsavel
        FOREIGN KEY (responsavel_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    CONSTRAINT fk_salas_criado_por
        FOREIGN KEY (criado_por) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE pecas (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    codigo        VARCHAR(40)  NOT NULL,
    descricao     VARCHAR(200) NOT NULL,
    quantidade    INT          NOT NULL DEFAULT 0,
    local_estoque VARCHAR(120) NULL,
    criado_por    INT NOT NULL,
    data_criacao  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pecas_criado_por
        FOREIGN KEY (criado_por) REFERENCES usuarios(id) ON DELETE CASCADE,
    UNIQUE KEY uq_pecas_codigo_admin (codigo, criado_por)
) ENGINE=InnoDB;

CREATE TABLE requisicoes (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    solicitante_id    INT NOT NULL,
    item_pedido       VARCHAR(200) NOT NULL,
    motivo            VARCHAR(255) NULL,
    status            ENUM('Pendente','Aprovado','Recusado') NOT NULL DEFAULT 'Pendente',
    data_solicitacao  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_requisicoes_solicitante
        FOREIGN KEY (solicitante_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE movimentacoes (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    peca_id     INT NOT NULL,
    destino     VARCHAR(120) NULL,
    status      ENUM('Concluído','Pendente','Cancelado') NOT NULL DEFAULT 'Concluído',
    data_hora   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mov_peca
        FOREIGN KEY (peca_id) REFERENCES pecas(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE logs (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id    INT NULL,
    acao          VARCHAR(255) NOT NULL,
    data_hora     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_logs_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB;

DELIMITER $$

CREATE TRIGGER trg_usuarios_limite_por_admin
BEFORE INSERT ON usuarios
FOR EACH ROW
BEGIN
    DECLARE qtd INT;
    IF NEW.tipo = 'usuario' AND NEW.criado_por IS NOT NULL THEN
        SELECT COUNT(*) INTO qtd
        FROM usuarios
        WHERE criado_por = NEW.criado_por;

        IF qtd >= 4 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Este administrador já atingiu o limite de 4 usuários cadastrados.';
        END IF;
    END IF;
END$$

DELIMITER ;

INSERT INTO usuarios (nome, login, senha_hash, cargo, tipo, criado_por) VALUES
('Administrador', 'admin', 'scrypt:32768:8:1$tpz56ByYTNHJKmOi$6fcc475b9a050cb5d5c038fab700217f82a98df6f1200f1f192ef490a6302e68d03b628013b9082680a7a5d9f1e3d092c8e6b51bb58b25d594ac623157d95ffa', 'Coordenador de TI', 'admin', NULL);

INSERT INTO usuarios (nome, login, senha_hash, cargo, tipo, criado_por) VALUES
('Usuário Padrão', 'user', 'scrypt:32768:8:1$xrz9Wrd6M7OVKFWs$66dd4153d9337bf16d8ad53146609e67edc9bda8c8b32a54412fb4038ae5a7681c61661cf1e954b939c2b63370611b024020def4c77fa90484520c22166a20a2', 'Técnico de TI', 'usuario', 1);

INSERT INTO logs (usuario_id, acao) VALUES (1, 'Banco de dados inicializado.');
