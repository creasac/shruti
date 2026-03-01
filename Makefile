.PHONY: install setup doctor daemon transcribe

install:
	./install.sh

setup:
	./.venv/bin/shruti setup

doctor:
	./.venv/bin/shruti doctor --verbose

daemon:
	./.venv/bin/shruti daemon

transcribe:
	./.venv/bin/shruti transcribe
