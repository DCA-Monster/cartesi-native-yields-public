.PHONY: test
test:
	rm -f test-dapp.sqlite*
	DB_FILE_PATH="test-dapp.sqlite"; \
	if [ -z "$(test_name)" ]; then \
		if [ "$(NO_COVERAGE)" != "1" ]; then \
			if [ "$(DEBUG)" = "true" ]; then \
				python -m debugpy --listen 5678 --wait-for-client -m coverage run -m unittest discover -s cartesi-dapp/tests; \
			else \
				coverage run -m unittest discover -s cartesi-dapp/tests; \
			fi; \
			coverage report; \
			coverage html; \
		else \
			if [ "$(DEBUG)" = "true" ]; then \
				python -m debugpy --listen 5678 --wait-for-client -m unittest discover -s cartesi-dapp/tests; \
			else \
				python -m unittest discover -s cartesi-dapp/tests; \
			fi; \
		fi; \
	else \
		if [ "$(NO_COVERAGE)" != "1" ]; then \
			if [ "$(DEBUG)" = "true" ]; then \
				python -m debugpy --listen 5680 --wait-for-client -m coverage run -m unittest discover -v -k "*$(test_name)*" cartesi-dapp/tests; \
			else \
				coverage run -m unittest discover -v -k "*$(test_name)*" cartesi-dapp/tests; \
			fi; \
			coverage report; \
			coverage html; \
		else \
			if [ "$(DEBUG)" = "true" ]; then \
				python -m debugpy --listen 5680 --wait-for-client -m unittest discover -v -k "*$(test_name)*" cartesi-dapp/tests; \
			else \
				python -m unittest discover -v -k "*$(test_name)*" cartesi-dapp/tests; \
			fi; \
		fi; \
	fi
