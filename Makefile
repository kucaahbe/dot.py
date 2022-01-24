SHELL=/bin/bash

test:
	@ARGS='-m unittest discover -s test'; \
	if hash coverage 2>/dev/null; then    \
	  echo coverage is enabled;           \
	  coverage run                        \
	    --source=.                        \
	    --omit='test/*'                   \
	    $$ARGS;                           \
	else                                  \
	  echo coverage is disabled;          \
	  python3 $$ARGS;                     \
	fi
.PHONY: test

test/report:
	@coverage html
	@if hash xdg-open 2>/dev/null; then CMD=xdg-open; else CMD=open; fi; \
	  $$CMD htmlcov/index.html 2>/dev/null
	@sleep 1 # wait for stdout output to appear and than return to cli prompt
.PHONY: test/report
