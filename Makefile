.PHONY: all forms zip clean format check prebuild install
all: zip

forms: src/form.py

PACKAGE_NAME := copy_around

zip: forms $(PACKAGE_NAME).ankiaddon

src/form.py: designer/form.ui
	pyuic5 $^ > $@

prebuild:
	rm -rf src/__pycache__

$(PACKAGE_NAME).ankiaddon: prebuild src/*
	rm -f $@
	rm -rf src/__pycache__
	( cd src/; zip -r ../$@ * )


# Install in test profile
install: prebuild forms
	rm -r ankiprofile/addons21/$(PACKAGE_NAME)
	cp -r src/. ankiprofile/addons21/$(PACKAGE_NAME)

format:
	python -m black src/

check:
	python -m mypy src/

clean:
	rm -f src/form.py
	rm -f $(PACKAGE_NAME).ankiaddon
