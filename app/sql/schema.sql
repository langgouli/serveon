-- 电商智能客服 Agent 数据库 schema
-- 库名：ziyan

CREATE DATABASE IF NOT EXISTS ziyan
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE ziyan;

-- 订单表
DROP TABLE IF EXISTS orders;
CREATE TABLE orders (
    order_number   VARCHAR(20)   NOT NULL PRIMARY KEY,
    user_id        INT           NOT NULL,
    amount         DECIMAL(10,2) NOT NULL,
    product        VARCHAR(100)  NOT NULL,
    category       VARCHAR(50)   NOT NULL,
    status         VARCHAR(20)   NOT NULL,
    signed_at      DATETIME      NULL,
    support_return TINYINT(1)    NOT NULL DEFAULT 1,
    INDEX idx_orders_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 物流表
DROP TABLE IF EXISTS logistics;
CREATE TABLE logistics (
    order_number      VARCHAR(20)   NOT NULL PRIMARY KEY,
    tracks            TEXT          NOT NULL COMMENT 'JSON: 物流轨迹数组',
    estimated_delivery DATETIME     NULL,
    abnormal          TINYINT(1)    NOT NULL DEFAULT 0,
    CONSTRAINT fk_logistics_order
        FOREIGN KEY (order_number) REFERENCES orders(order_number) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 政策表
DROP TABLE IF EXISTS policies;
CREATE TABLE policies (
    clause_id   INT          NOT NULL PRIMARY KEY,
    title       VARCHAR(100) NOT NULL,
    category    VARCHAR(20)  NOT NULL,
    content     TEXT         NOT NULL,
    keywords    VARCHAR(255) NOT NULL COMMENT '逗号分隔关键词',
    INDEX idx_policies_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 退款记录表
DROP TABLE IF EXISTS refunds;
CREATE TABLE refunds (
    id             BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    session_id     VARCHAR(64)  NOT NULL,
    order_number   VARCHAR(20)  NOT NULL,
    user_id        INT          NULL,
    request_type   VARCHAR(32)  NOT NULL,
    amount         DECIMAL(10,2) NOT NULL,
    reason         VARCHAR(255) NULL,
    refund_status  VARCHAR(32)  NOT NULL COMMENT 'processing/done/blocked/cancelled',
    refund_no      VARCHAR(32)  NULL COMMENT '业务退款单号',
    refund_record  TEXT         NULL COMMENT 'JSON：完整退款记录',
    created_at     DATETIME     NOT NULL,
    INDEX idx_refunds_session (session_id),
    INDEX idx_refunds_order   (order_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
