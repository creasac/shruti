.PHONY: install setup doctor oneshot transcribe

install:
	./install.sh

setup:
	$(HOME)/.local/bin/shruti setup

doctor:
	$(HOME)/.local/bin/shruti doctor --verbose

oneshot:
	$(HOME)/.local/bin/shruti oneshot

transcribe:
	$(HOME)/.local/bin/shruti transcribe
