HOST ?= http://localhost:8080

.PHONY: stress-test oversell-test orders-test mixed-test ratelimit-test s3-test

stress-test:
	uv run locust \
		-f load_tests/locustfile.py \
		--headless \
		--users 500 \
		--spawn-rate 100 \
		--run-time 60s \
		--host $(HOST)

oversell-test:
	DB_HOST=localhost uv run python scripts/seed_oversell_product.py
	uv run locust \
		-f load_tests/locustfile_oversell.py \
		--headless \
		--users 100 \
		--spawn-rate 50 \
		--run-time 60s \
		--host $(HOST)

orders-test:
	uv run locust \
		-f load_tests/locustfile_orders.py \
		--headless \
		--users 100 \
		--spawn-rate 50 \
		--run-time 60s \
		--host $(HOST)

mixed-test:
	uv run locust \
		-f load_tests/locustfile_mixed.py \
		--headless \
		--users 100 \
		--spawn-rate 50 \
		--run-time 60s \
		--host $(HOST)

ratelimit-test:
	uv run locust \
		-f load_tests/locustfile_ratelimit.py \
		--headless \
		--users 1 \
		--spawn-rate 1 \
		--run-time 15s \
		--host $(HOST)

s3-test:
	uv run locust \
		-f load_tests/locustfile_s3.py \
		--headless \
		--users 50 \
		--spawn-rate 10 \
		--run-time 20s \
		--host $(HOST)
