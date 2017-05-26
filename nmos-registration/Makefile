PYTHON=`which python`
DESTDIR=/
PROJECT=nmos-registration

all:
	@echo "make source - Create source package"
	@echo "make install - Install on local system (only during development)"
	@echo "make deb - Generate a deb package - for local testing"
	@echo "make clean - Get rid of scratch and byte files"
	@echo "make test - Run any unit tests"

source:
	$(PYTHON) setup.py sdist $(COMPILE)

install:
	$(PYTHON) setup.py install --root $(DESTDIR) $(COMPILE)

deb:
	debuild -uc -us

clean:
	$(PYTHON) setup.py clean
	dh_clean
	rm -rf build/ MANIFEST
	find . -name '*.pyc' -delete

test:
	$(PYTHON) -m unittest discover
