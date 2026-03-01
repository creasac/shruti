.PHONY: install setup doctor oneshot transcribe

install:
	./install.sh

setup:
	./.venv/bin/shruti setup

doctor:
	./.venv/bin/shruti doctor --verbose

oneshot:
	./.venv/bin/shruti oneshot

transcribe:
	./.venv/bin/shruti transcribe
