SHELL=/bin/bash

test:
	@ARGS='-m unittest discover -s test'; \
	if hash coverage 2>/dev/null; then    \
	  echo coverage is enabled;           \
	  coverage run                        \
	    --source=.                        \
	    --omit='test/*'                   \
	    $$ARGS;                           \
	  code=$$?;                           \
	  coverage html;                      \
	  exit $$code;                        \
	else                                  \
	  echo coverage is disabled;          \
	  python3 $$ARGS;                     \
	fi
.PHONY: test

lint:
	pylint --jobs=0 dotfiles.py test/*.py
.PHONY: lint
