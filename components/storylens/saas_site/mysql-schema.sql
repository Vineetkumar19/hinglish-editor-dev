-- Storylens MySQL 8.0+ schema. No passwords or customer records.


CREATE TABLE device_codes (
	code VARCHAR(64) NOT NULL, 
	user_code VARCHAR(9) NOT NULL, 
	edition VARCHAR(20) NOT NULL, 
	public_key VARCHAR(44) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	expires FLOAT(53) NOT NULL, 
	user_id VARCHAR(64), 
	consumed INTEGER NOT NULL DEFAULT '0', 
	hardware_hash VARCHAR(64) NOT NULL DEFAULT '', 
	PRIMARY KEY (code), 
	UNIQUE (user_code)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE license_nonces (
	device_id VARCHAR(64) NOT NULL, 
	nonce VARCHAR(64) NOT NULL, 
	expires FLOAT(53) NOT NULL, 
	PRIMARY KEY (device_id, nonce)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE rate_limits (
	`key` VARCHAR(255) NOT NULL, 
	bucket BIGINT NOT NULL, 
	count INTEGER NOT NULL, 
	expires FLOAT(53) NOT NULL DEFAULT '0', 
	PRIMARY KEY (`key`, bucket)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE revocations (
	payment_id VARCHAR(90) NOT NULL, 
	created FLOAT(53) NOT NULL, 
	PRIMARY KEY (payment_id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE security_events (
	id VARCHAR(64) NOT NULL, 
	actor VARCHAR(64) NOT NULL, 
	action TEXT NOT NULL, 
	target VARCHAR(100) NOT NULL, 
	created FLOAT(53) NOT NULL, 
	PRIMARY KEY (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE support_outbox (
	id VARCHAR(64) NOT NULL, 
	recipient VARCHAR(254) NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	body TEXT NOT NULL, 
	state VARCHAR(20) NOT NULL DEFAULT 'pending', 
	attempts INTEGER NOT NULL DEFAULT '0', 
	available FLOAT(53) NOT NULL, 
	lease_until FLOAT(53) NOT NULL DEFAULT '0', 
	claim VARCHAR(64), 
	created FLOAT(53) NOT NULL, 
	PRIMARY KEY (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE transaction_lock (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	PRIMARY KEY (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE users (
	id VARCHAR(64) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password VARCHAR(255) NOT NULL, 
	verified INTEGER NOT NULL DEFAULT '0', 
	created FLOAT(53) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE webhook_events (
	id VARCHAR(64) NOT NULL, 
	created FLOAT(53) NOT NULL, 
	PRIMARY KEY (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE computer_bindings (
	user_id VARCHAR(64) NOT NULL, 
	public_key VARCHAR(44), 
	hardware_hash VARCHAR(64), 
	release_after FLOAT(53) NOT NULL DEFAULT '0', 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE device_bindings (
	user_id VARCHAR(64) NOT NULL, 
	edition VARCHAR(20) NOT NULL, 
	device_id VARCHAR(64), 
	release_after FLOAT(53) NOT NULL DEFAULT '0', 
	PRIMARY KEY (user_id, edition), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE devices (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	edition VARCHAR(20) NOT NULL, 
	public_key VARCHAR(44) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	credential VARCHAR(64) NOT NULL, 
	revoked INTEGER NOT NULL DEFAULT '0', 
	created FLOAT(53) NOT NULL, 
	hardware_hash VARCHAR(64) NOT NULL DEFAULT '', 
	last_lease FLOAT(53) NOT NULL DEFAULT '0', 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE jobs (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	tool VARCHAR(30) NOT NULL, 
	payload TEXT NOT NULL, 
	state VARCHAR(20) NOT NULL DEFAULT 'queued', 
	message VARCHAR(1000) NOT NULL DEFAULT 'Waiting for the rendering worker', 
	created FLOAT(53) NOT NULL, 
	updated FLOAT(53) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE orders (
	id VARCHAR(90) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	plan VARCHAR(20) NOT NULL, 
	amount BIGINT NOT NULL, 
	currency VARCHAR(5) NOT NULL DEFAULT 'INR', 
	state VARCHAR(20) NOT NULL DEFAULT 'created', 
	payment_id VARCHAR(90), 
	starts FLOAT(53), 
	ends FLOAT(53), 
	created FLOAT(53) NOT NULL, 
	edition VARCHAR(20) NOT NULL DEFAULT 'bundle', 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	UNIQUE (payment_id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE reviews (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	display_name VARCHAR(60) NOT NULL, 
	rating INTEGER NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	body TEXT NOT NULL, 
	status VARCHAR(20) NOT NULL DEFAULT 'pending', 
	created FLOAT(53) NOT NULL, 
	updated FLOAT(53) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE sessions (
	token VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	csrf VARCHAR(64) NOT NULL, 
	expires FLOAT(53) NOT NULL, 
	PRIMARY KEY (token), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE support_tickets (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	subject VARCHAR(140) NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	status VARCHAR(20) NOT NULL DEFAULT 'open', 
	created FLOAT(53) NOT NULL, 
	updated FLOAT(53) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE tokens (
	hash VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	expires FLOAT(53) NOT NULL, 
	PRIMARY KEY (hash), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE uploads (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	path TEXT NOT NULL, 
	bytes BIGINT NOT NULL, 
	created FLOAT(53) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE exports (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	job_id VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	path TEXT NOT NULL, 
	created FLOAT(53) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(job_id) REFERENCES jobs (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE support_messages (
	id VARCHAR(64) NOT NULL, 
	ticket_id VARCHAR(64) NOT NULL, 
	author VARCHAR(64) NOT NULL, 
	staff INTEGER NOT NULL DEFAULT '0', 
	body TEXT NOT NULL, 
	created FLOAT(53) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ticket_id) REFERENCES support_tickets (id), 
	FOREIGN KEY(author) REFERENCES users (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;


CREATE TABLE usage_events (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	device_id VARCHAR(64) NOT NULL, 
	tool VARCHAR(30) NOT NULL, 
	outcome VARCHAR(20) NOT NULL, 
	duration FLOAT(53) NOT NULL, 
	app_version VARCHAR(30) NOT NULL, 
	created FLOAT(53) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(device_id) REFERENCES devices (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_bin

;

CREATE INDEX ix_sessions_lookup ON sessions (user_id, expires);

CREATE INDEX ix_orders_lookup ON orders (user_id, state, ends);

CREATE INDEX ix_uploads_lookup ON uploads (user_id);

CREATE INDEX ix_jobs_lookup ON jobs (user_id, created);

CREATE INDEX ix_devices_lookup ON devices (user_id, revoked);

CREATE INDEX ix_support_tickets_lookup ON support_tickets (user_id, updated);

CREATE INDEX ix_support_outbox_lookup ON support_outbox (state, available);

CREATE INDEX ix_reviews_lookup ON reviews (status, updated);

CREATE INDEX ix_usage_events_lookup ON usage_events (user_id, created);

INSERT IGNORE INTO transaction_lock(id) VALUES(1);